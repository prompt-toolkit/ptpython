"""
Application for reading Python input.
This can be used for creation of Python REPLs.
"""
import __future__

from asyncio import get_event_loop
from functools import partial
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.auto_suggest import (
    AutoSuggestFromHistory,
    ConditionalAutoSuggest,
    ThreadedAutoSuggest,
)
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, FuzzyCompleter, ThreadedCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER, EditingMode
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import (
    FileHistory,
    History,
    InMemoryHistory,
    ThreadedHistory,
)
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import (
    ConditionalKeyBindings,
    KeyBindings,
    merge_key_bindings,
)
from prompt_toolkit.key_binding.bindings.auto_suggest import load_auto_suggest_bindings
from prompt_toolkit.key_binding.bindings.open_in_editor import (
    load_open_in_editor_bindings,
)
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.lexers import DynamicLexer, Lexer, PygmentsLexer, SimpleLexer
from prompt_toolkit.output import ColorDepth, Output
from prompt_toolkit.styles import (
    AdjustBrightnessStyleTransformation,
    BaseStyle,
    ConditionalStyleTransformation,
    DynamicStyle,
    SwapLightAndDarkStyleTransformation,
    merge_style_transformations,
)
from prompt_toolkit.utils import is_windows
from prompt_toolkit.validation import ConditionalValidator, Validator
from pygments.lexers import Python3Lexer as PythonLexer

from .completer import PythonCompleter
from .history_browser import PythonHistory
from .key_bindings import (
    load_confirm_exit_bindings,
    load_python_bindings,
    load_sidebar_bindings,
)
from .layout import CompletionVisualisation, PtPythonLayout
from .prompt_style import ClassicPrompt, IPythonPrompt, PromptStyle
from .style import generate_style, get_all_code_styles, get_all_ui_styles
from .utils import get_jedi_script_from_document
from .validator import PythonValidator

__all__ = ["PythonInput"]

_T = TypeVar("_T")


class OptionCategory:
    def __init__(self, title: str, options: List["Option"]) -> None:
        self.title = title
        self.options = options


class Option(Generic[_T]):
    """
    Ptpython configuration option that can be shown and modified from the
    sidebar.

    :param title: Text.
    :param description: Text.
    :param get_values: Callable that returns a dictionary mapping the
            possible values to callbacks that activate these value.
    :param get_current_value: Callable that returns the current, active value.
    """

    def __init__(
        self,
        title: str,
        description: str,
        get_current_value: Callable[[], _T],
        # We accept `object` as return type for the select functions, because
        # often they return an unused boolean. Maybe this can be improved.
        get_values: Callable[[], Dict[_T, Callable[[], object]]],
    ) -> None:
        self.title = title
        self.description = description
        self.get_current_value = get_current_value
        self.get_values = get_values

    @property
    def values(self) -> Dict[_T, Callable[[], object]]:
        return self.get_values()

    def activate_next(self, _previous: bool = False) -> None:
        """
        Activate next value.
        """
        current = self.get_current_value()
        options = sorted(self.values.keys())

        # Get current index.
        try:
            index = options.index(current)
        except ValueError:
            index = 0

        # Go to previous/next index.
        if _previous:
            index -= 1
        else:
            index += 1

        # Call handler for this option.
        next_option = options[index % len(options)]
        self.values[next_option]()

    def activate_previous(self) -> None:
        """
        Activate previous value.
        """
        self.activate_next(_previous=True)


COLOR_DEPTHS = {
    ColorDepth.DEPTH_1_BIT: "Monochrome",
    ColorDepth.DEPTH_4_BIT: "ANSI Colors",
    ColorDepth.DEPTH_8_BIT: "256 colors",
    ColorDepth.DEPTH_24_BIT: "True color",
}

_Namespace = Dict[str, Any]
_GetNamespace = Callable[[], _Namespace]


class PythonInput:
    """
    Prompt for reading Python input.

    ::

        python_input = PythonInput(...)
        python_code = python_input.app.run()
    """

    def __init__(
        self,
        get_globals: Optional[_GetNamespace] = None,
        get_locals: Optional[_GetNamespace] = None,
        history_filename: Optional[str] = None,
        vi_mode: bool = False,
        color_depth: Optional[ColorDepth] = None,
        # Input/output.
        input: Optional[Input] = None,
        output: Optional[Output] = None,
        # For internal use.
        extra_key_bindings: Optional[KeyBindings] = None,
        _completer: Optional[Completer] = None,
        _validator: Optional[Validator] = None,
        _lexer: Optional[Lexer] = None,
        _extra_buffer_processors=None,
        _extra_layout_body=None,
        _extra_toolbars=None,
        _input_buffer_height=None,
    ) -> None:

        self.get_globals: _GetNamespace = get_globals or (lambda: {})
        self.get_locals: _GetNamespace = get_locals or self.get_globals

        self._completer = _completer or FuzzyCompleter(
            PythonCompleter(
                self.get_globals,
                self.get_locals,
                lambda: self.enable_dictionary_completion,
            ),
            enable_fuzzy=Condition(lambda: self.enable_fuzzy_completion),
        )
        self._validator = _validator or PythonValidator(self.get_compiler_flags)
        self._lexer = _lexer or PygmentsLexer(PythonLexer)

        self.history: History
        if history_filename:
            self.history = ThreadedHistory(FileHistory(history_filename))
        else:
            self.history = InMemoryHistory()

        self._input_buffer_height = _input_buffer_height
        self._extra_layout_body = _extra_layout_body or []
        self._extra_toolbars = _extra_toolbars or []
        self._extra_buffer_processors = _extra_buffer_processors or []

        self.extra_key_bindings = extra_key_bindings or KeyBindings()

        # Settings.
        self.show_signature: bool = False
        self.show_docstring: bool = False
        self.show_meta_enter_message: bool = True
        self.completion_visualisation: CompletionVisualisation = CompletionVisualisation.MULTI_COLUMN
        self.completion_menu_scroll_offset: int = 1

        self.show_line_numbers: bool = False
        self.show_status_bar: bool = True
        self.wrap_lines: bool = True
        self.complete_while_typing: bool = True
        self.paste_mode: bool = False  # When True, don't insert whitespace after newline.
        self.confirm_exit: bool = True  # Ask for confirmation when Control-D is pressed.
        self.accept_input_on_enter: int = 2  # Accept when pressing Enter 'n' times.
        # 'None' means that meta-enter is always required.
        self.enable_open_in_editor: bool = True
        self.enable_system_bindings: bool = True
        self.enable_input_validation: bool = True
        self.enable_auto_suggest: bool = False
        self.enable_mouse_support: bool = False
        self.enable_history_search: bool = False  # When True, like readline, going
        # back in history will filter the
        # history on the records starting
        # with the current input.

        self.enable_syntax_highlighting: bool = True
        self.enable_fuzzy_completion: bool = False
        self.enable_dictionary_completion: bool = False
        self.swap_light_and_dark: bool = False
        self.highlight_matching_parenthesis: bool = False
        self.show_sidebar: bool = False  # Currently show the sidebar.

        # When the sidebar is visible, also show the help text.
        self.show_sidebar_help: bool = True

        # Currently show 'Do you really want to exit?'
        self.show_exit_confirmation: bool = False

        # The title to be displayed in the terminal. (None or string.)
        self.terminal_title: Optional[str] = None

        self.exit_message: str = "Do you really want to exit?"
        self.insert_blank_line_after_output: bool = True  # (For the REPL.)

        # The buffers.
        self.default_buffer = self._create_buffer()
        self.search_buffer: Buffer = Buffer()
        self.docstring_buffer: Buffer = Buffer(read_only=True)

        # Tokens to be shown at the prompt.
        self.prompt_style: str = "classic"  # The currently active style.

        # Styles selectable from the menu.
        self.all_prompt_styles: Dict[str, PromptStyle] = {
            "ipython": IPythonPrompt(self),
            "classic": ClassicPrompt(),
        }

        self.get_input_prompt = lambda: self.all_prompt_styles[
            self.prompt_style
        ].in_prompt()

        self.get_output_prompt = lambda: self.all_prompt_styles[
            self.prompt_style
        ].out_prompt()

        #: Load styles.
        self.code_styles: Dict[str, BaseStyle] = get_all_code_styles()
        self.ui_styles = get_all_ui_styles()
        self._current_code_style_name: str = "default"
        self._current_ui_style_name: str = "default"

        if is_windows():
            self._current_code_style_name = "win32"

        self._current_style = self._generate_style()
        self.color_depth: ColorDepth = color_depth or ColorDepth.default()

        self.max_brightness: float = 1.0
        self.min_brightness: float = 0.0

        # Options to be configurable from the sidebar.
        self.options = self._create_options()
        self.selected_option_index: int = 0

        #: Incremeting integer counting the current statement.
        self.current_statement_index: int = 1

        # Code signatures. (This is set asynchronously after a timeout.)
        self.signatures: List[Any] = []

        # Boolean indicating whether we have a signatures thread running.
        # (Never run more than one at the same time.)
        self._get_signatures_thread_running: bool = False

        self.style_transformation = merge_style_transformations(
            [
                ConditionalStyleTransformation(
                    SwapLightAndDarkStyleTransformation(),
                    filter=Condition(lambda: self.swap_light_and_dark),
                ),
                AdjustBrightnessStyleTransformation(
                    lambda: self.min_brightness, lambda: self.max_brightness
                ),
            ]
        )
        self.ptpython_layout = PtPythonLayout(
            self,
            lexer=DynamicLexer(
                lambda: self._lexer
                if self.enable_syntax_highlighting
                else SimpleLexer()
            ),
            input_buffer_height=self._input_buffer_height,
            extra_buffer_processors=self._extra_buffer_processors,
            extra_body=self._extra_layout_body,
            extra_toolbars=self._extra_toolbars,
        )

        self.app = self._create_application()

        if vi_mode:
            self.app.editing_mode = EditingMode.VI

    def _accept_handler(self, buff: Buffer) -> bool:
        app = get_app()
        app.exit(result=buff.text)
        app.pre_run_callables.append(buff.reset)
        return True  # Keep text, we call 'reset' later on.

    @property
    def option_count(self) -> int:
        " Return the total amount of options. (In all categories together.) "
        return sum(len(category.options) for category in self.options)

    @property
    def selected_option(self) -> Option:
        " Return the currently selected option. "
        i = 0
        for category in self.options:
            for o in category.options:
                if i == self.selected_option_index:
                    return o
                else:
                    i += 1

        raise ValueError("Nothing selected")

    def get_compiler_flags(self) -> int:
        """
        Give the current compiler flags by looking for _Feature instances
        in the globals.
        """
        flags = 0

        for value in self.get_globals().values():
            if isinstance(value, __future__._Feature):
                flags |= value.compiler_flag

        return flags

    @property
    def add_key_binding(self) -> Callable[[_T], _T]:
        """
        Shortcut for adding new key bindings.
        (Mostly useful for a config.py file, that receives
        a PythonInput/Repl instance as input.)

        ::

            @python_input.add_key_binding(Keys.ControlX, filter=...)
            def handler(event):
                ...
        """

        def add_binding_decorator(*k, **kw):
            return self.extra_key_bindings.add(*k, **kw)

        return add_binding_decorator

    def install_code_colorscheme(self, name: str, style: BaseStyle) -> None:
        """
        Install a new code color scheme.
        """
        self.code_styles[name] = style

    def use_code_colorscheme(self, name: str) -> None:
        """
        Apply new colorscheme. (By name.)
        """
        assert name in self.code_styles

        self._current_code_style_name = name
        self._current_style = self._generate_style()

    def install_ui_colorscheme(self, name: str, style: BaseStyle) -> None:
        """
        Install a new UI color scheme.
        """
        self.ui_styles[name] = style

    def use_ui_colorscheme(self, name: str) -> None:
        """
        Apply new colorscheme. (By name.)
        """
        assert name in self.ui_styles

        self._current_ui_style_name = name
        self._current_style = self._generate_style()

    def _use_color_depth(self, depth: ColorDepth) -> None:
        self.color_depth = depth

    def _set_min_brightness(self, value: float) -> None:
        self.min_brightness = value
        self.max_brightness = max(self.max_brightness, value)

    def _set_max_brightness(self, value: float) -> None:
        self.max_brightness = value
        self.min_brightness = min(self.min_brightness, value)

    def _generate_style(self) -> BaseStyle:
        """
        Create new Style instance.
        (We don't want to do this on every key press, because each time the
        renderer receives a new style class, he will redraw everything.)
        """
        return generate_style(
            self.code_styles[self._current_code_style_name],
            self.ui_styles[self._current_ui_style_name],
        )

    def _create_options(self) -> List[OptionCategory]:
        """
        Create a list of `Option` instances for the options sidebar.
        """

        def enable(attribute: str, value: Any = True) -> bool:
            setattr(self, attribute, value)

            # Return `True`, to be able to chain this in the lambdas below.
            return True

        def disable(attribute: str) -> bool:
            setattr(self, attribute, False)
            return True

        def simple_option(
            title: str, description: str, field_name: str, values: Optional[List] = None
        ) -> Option:
            " Create Simple on/of option. "
            values = values or ["off", "on"]

            def get_current_value():
                return values[bool(getattr(self, field_name))]

            def get_values():
                return {
                    values[1]: lambda: enable(field_name),
                    values[0]: lambda: disable(field_name),
                }

            return Option(
                title=title,
                description=description,
                get_values=get_values,
                get_current_value=get_current_value,
            )

        brightness_values = [1.0 / 20 * value for value in range(0, 21)]

        return [
            OptionCategory(
                "Input",
                [
                    Option(
                        title="Editing mode",
                        description="Vi or emacs key bindings.",
                        get_current_value=lambda: ["Emacs", "Vi"][self.vi_mode],
                        get_values=lambda: {
                            "Emacs": lambda: disable("vi_mode"),
                            "Vi": lambda: enable("vi_mode"),
                        },
                    ),
                    simple_option(
                        title="Paste mode",
                        description="When enabled, don't indent automatically.",
                        field_name="paste_mode",
                    ),
                    Option(
                        title="Complete while typing",
                        description="Generate autocompletions automatically while typing. "
                        'Don\'t require pressing TAB. (Not compatible with "History search".)',
                        get_current_value=lambda: ["off", "on"][
                            self.complete_while_typing
                        ],
                        get_values=lambda: {
                            "on": lambda: enable("complete_while_typing")
                            and disable("enable_history_search"),
                            "off": lambda: disable("complete_while_typing"),
                        },
                    ),
                    Option(
                        title="Enable fuzzy completion",
                        description="Enable fuzzy completion.",
                        get_current_value=lambda: ["off", "on"][
                            self.enable_fuzzy_completion
                        ],
                        get_values=lambda: {
                            "on": lambda: enable("enable_fuzzy_completion"),
                            "off": lambda: disable("enable_fuzzy_completion"),
                        },
                    ),
                    Option(
                        title="Dictionary completion",
                        description="Enable experimental dictionary completion.\n"
                        'WARNING: this does "eval" on fragments of\n'
                        "         your Python input and is\n"
                        "         potentially unsafe.",
                        get_current_value=lambda: ["off", "on"][
                            self.enable_dictionary_completion
                        ],
                        get_values=lambda: {
                            "on": lambda: enable("enable_dictionary_completion"),
                            "off": lambda: disable("enable_dictionary_completion"),
                        },
                    ),
                    Option(
                        title="History search",
                        description="When pressing the up-arrow, filter the history on input starting "
                        'with the current text. (Not compatible with "Complete while typing".)',
                        get_current_value=lambda: ["off", "on"][
                            self.enable_history_search
                        ],
                        get_values=lambda: {
                            "on": lambda: enable("enable_history_search")
                            and disable("complete_while_typing"),
                            "off": lambda: disable("enable_history_search"),
                        },
                    ),
                    simple_option(
                        title="Mouse support",
                        description="Respond to mouse clicks and scrolling for positioning the cursor, "
                        "selecting text and scrolling through windows.",
                        field_name="enable_mouse_support",
                    ),
                    simple_option(
                        title="Confirm on exit",
                        description="Require confirmation when exiting.",
                        field_name="confirm_exit",
                    ),
                    simple_option(
                        title="Input validation",
                        description="In case of syntax errors, move the cursor to the error "
                        "instead of showing a traceback of a SyntaxError.",
                        field_name="enable_input_validation",
                    ),
                    simple_option(
                        title="Auto suggestion",
                        description="Auto suggest inputs by looking at the history. "
                        "Pressing right arrow or Ctrl-E will complete the entry.",
                        field_name="enable_auto_suggest",
                    ),
                    Option(
                        title="Accept input on enter",
                        description="Amount of ENTER presses required to execute input when the cursor "
                        "is at the end of the input. (Note that META+ENTER will always execute.)",
                        get_current_value=lambda: str(
                            self.accept_input_on_enter or "meta-enter"
                        ),
                        get_values=lambda: {
                            "2": lambda: enable("accept_input_on_enter", 2),
                            "3": lambda: enable("accept_input_on_enter", 3),
                            "4": lambda: enable("accept_input_on_enter", 4),
                            "meta-enter": lambda: enable("accept_input_on_enter", None),
                        },
                    ),
                ],
            ),
            OptionCategory(
                "Display",
                [
                    Option(
                        title="Completions",
                        description="Visualisation to use for displaying the completions. (Multiple columns, one column, a toolbar or nothing.)",
                        get_current_value=lambda: self.completion_visualisation.value,
                        get_values=lambda: {
                            CompletionVisualisation.NONE.value: lambda: enable(
                                "completion_visualisation", CompletionVisualisation.NONE
                            ),
                            CompletionVisualisation.POP_UP.value: lambda: enable(
                                "completion_visualisation",
                                CompletionVisualisation.POP_UP,
                            ),
                            CompletionVisualisation.MULTI_COLUMN.value: lambda: enable(
                                "completion_visualisation",
                                CompletionVisualisation.MULTI_COLUMN,
                            ),
                            CompletionVisualisation.TOOLBAR.value: lambda: enable(
                                "completion_visualisation",
                                CompletionVisualisation.TOOLBAR,
                            ),
                        },
                    ),
                    Option(
                        title="Prompt",
                        description="Visualisation of the prompt. ('>>>' or 'In [1]:')",
                        get_current_value=lambda: self.prompt_style,
                        get_values=lambda: dict(
                            (s, partial(enable, "prompt_style", s))
                            for s in self.all_prompt_styles
                        ),
                    ),
                    simple_option(
                        title="Blank line after output",
                        description="Insert a blank line after the output.",
                        field_name="insert_blank_line_after_output",
                    ),
                    simple_option(
                        title="Show signature",
                        description="Display function signatures.",
                        field_name="show_signature",
                    ),
                    simple_option(
                        title="Show docstring",
                        description="Display function docstrings.",
                        field_name="show_docstring",
                    ),
                    simple_option(
                        title="Show line numbers",
                        description="Show line numbers when the input consists of multiple lines.",
                        field_name="show_line_numbers",
                    ),
                    simple_option(
                        title="Show Meta+Enter message",
                        description="Show the [Meta+Enter] message when this key combination is required to execute commands. "
                        + "(This is the case when a simple [Enter] key press will insert a newline.",
                        field_name="show_meta_enter_message",
                    ),
                    simple_option(
                        title="Wrap lines",
                        description="Wrap lines instead of scrolling horizontally.",
                        field_name="wrap_lines",
                    ),
                    simple_option(
                        title="Show status bar",
                        description="Show the status bar at the bottom of the terminal.",
                        field_name="show_status_bar",
                    ),
                    simple_option(
                        title="Show sidebar help",
                        description="When the sidebar is visible, also show this help text.",
                        field_name="show_sidebar_help",
                    ),
                    simple_option(
                        title="Highlight parenthesis",
                        description="Highlight matching parenthesis, when the cursor is on or right after one.",
                        field_name="highlight_matching_parenthesis",
                    ),
                ],
            ),
            OptionCategory(
                "Colors",
                [
                    simple_option(
                        title="Syntax highlighting",
                        description="Use colors for syntax highligthing",
                        field_name="enable_syntax_highlighting",
                    ),
                    simple_option(
                        title="Swap light/dark colors",
                        description="Swap light and dark colors.",
                        field_name="swap_light_and_dark",
                    ),
                    Option(
                        title="Code",
                        description="Color scheme to use for the Python code.",
                        get_current_value=lambda: self._current_code_style_name,
                        get_values=lambda: {
                            name: partial(self.use_code_colorscheme, name)
                            for name in self.code_styles
                        },
                    ),
                    Option(
                        title="User interface",
                        description="Color scheme to use for the user interface.",
                        get_current_value=lambda: self._current_ui_style_name,
                        get_values=lambda: dict(
                            (name, partial(self.use_ui_colorscheme, name))
                            for name in self.ui_styles
                        ),
                    ),
                    Option(
                        title="Color depth",
                        description="Monochrome (1 bit), 16 ANSI colors (4 bit),\n256 colors (8 bit), or 24 bit.",
                        get_current_value=lambda: COLOR_DEPTHS[self.color_depth],
                        get_values=lambda: {
                            name: partial(self._use_color_depth, depth)
                            for depth, name in COLOR_DEPTHS.items()
                        },
                    ),
                    Option(
                        title="Min brightness",
                        description="Minimum brightness for the color scheme (default=0.0).",
                        get_current_value=lambda: "%.2f" % self.min_brightness,
                        get_values=lambda: {
                            "%.2f" % value: partial(self._set_min_brightness, value)
                            for value in brightness_values
                        },
                    ),
                    Option(
                        title="Max brightness",
                        description="Maximum brightness for the color scheme (default=1.0).",
                        get_current_value=lambda: "%.2f" % self.max_brightness,
                        get_values=lambda: {
                            "%.2f" % value: partial(self._set_max_brightness, value)
                            for value in brightness_values
                        },
                    ),
                ],
            ),
        ]

    def _create_application(self) -> Application:
        """
        Create an `Application` instance.
        """
        return Application(
            layout=self.ptpython_layout.layout,
            key_bindings=merge_key_bindings(
                [
                    load_python_bindings(self),
                    load_auto_suggest_bindings(),
                    load_sidebar_bindings(self),
                    load_confirm_exit_bindings(self),
                    ConditionalKeyBindings(
                        load_open_in_editor_bindings(),
                        Condition(lambda: self.enable_open_in_editor),
                    ),
                    # Extra key bindings should not be active when the sidebar is visible.
                    ConditionalKeyBindings(
                        self.extra_key_bindings,
                        Condition(lambda: not self.show_sidebar),
                    ),
                ]
            ),
            color_depth=lambda: self.color_depth,
            paste_mode=Condition(lambda: self.paste_mode),
            mouse_support=Condition(lambda: self.enable_mouse_support),
            style=DynamicStyle(lambda: self._current_style),
            style_transformation=self.style_transformation,
            include_default_pygments_style=False,
            reverse_vi_search_direction=True,
        )

    def _create_buffer(self) -> Buffer:
        """
        Create the `Buffer` for the Python input.
        """
        python_buffer = Buffer(
            name=DEFAULT_BUFFER,
            complete_while_typing=Condition(lambda: self.complete_while_typing),
            enable_history_search=Condition(lambda: self.enable_history_search),
            tempfile_suffix=".py",
            history=self.history,
            completer=ThreadedCompleter(self._completer),
            validator=ConditionalValidator(
                self._validator, Condition(lambda: self.enable_input_validation)
            ),
            auto_suggest=ConditionalAutoSuggest(
                ThreadedAutoSuggest(AutoSuggestFromHistory()),
                Condition(lambda: self.enable_auto_suggest),
            ),
            accept_handler=self._accept_handler,
            on_text_changed=self._on_input_timeout,
        )

        return python_buffer

    @property
    def editing_mode(self) -> EditingMode:
        return self.app.editing_mode

    @editing_mode.setter
    def editing_mode(self, value: EditingMode) -> None:
        self.app.editing_mode = value

    @property
    def vi_mode(self) -> bool:
        return self.editing_mode == EditingMode.VI

    @vi_mode.setter
    def vi_mode(self, value: bool) -> None:
        if value:
            self.editing_mode = EditingMode.VI
        else:
            self.editing_mode = EditingMode.EMACS

    def _on_input_timeout(self, buff: Buffer, loop=None) -> None:
        """
        When there is no input activity,
        in another thread, get the signature of the current code.
        """
        app = self.app

        # Never run multiple get-signature threads.
        if self._get_signatures_thread_running:
            return
        self._get_signatures_thread_running = True

        document = buff.document

        loop = loop or get_event_loop()

        def run():
            script = get_jedi_script_from_document(
                document, self.get_locals(), self.get_globals()
            )

            # Show signatures in help text.
            if script:
                try:
                    signatures = script.call_signatures()
                except ValueError:
                    # e.g. in case of an invalid \\x escape.
                    signatures = []
                except Exception:
                    # Sometimes we still get an exception (TypeError), because
                    # of probably bugs in jedi. We can silence them.
                    # See: https://github.com/davidhalter/jedi/issues/492
                    signatures = []
                else:
                    # Try to access the params attribute just once. For Jedi
                    # signatures containing the keyword-only argument star,
                    # this will crash when retrieving it the first time with
                    # AttributeError. Every following time it works.
                    # See: https://github.com/jonathanslenders/ptpython/issues/47
                    #      https://github.com/davidhalter/jedi/issues/598
                    try:
                        if signatures:
                            signatures[0].params
                    except AttributeError:
                        pass
            else:
                signatures = []

            self._get_signatures_thread_running = False

            # Set signatures and redraw if the text didn't change in the
            # meantime. Otherwise request new signatures.
            if buff.text == document.text:
                self.signatures = signatures

                # Set docstring in docstring buffer.
                if signatures:
                    string = signatures[0].docstring()
                    if not isinstance(string, str):
                        string = string.decode("utf-8")
                    self.docstring_buffer.reset(
                        document=Document(string, cursor_position=0)
                    )
                else:
                    self.docstring_buffer.reset()

                app.invalidate()
            else:
                self._on_input_timeout(buff, loop=loop)

        loop.run_in_executor(None, run)

    def on_reset(self) -> None:
        self.signatures = []

    def enter_history(self) -> None:
        """
        Display the history.
        """
        app = get_app()
        app.vi_state.input_mode = InputMode.NAVIGATION

        history = PythonHistory(self, self.default_buffer.document)

        from prompt_toolkit.application import in_terminal
        import asyncio

        async def do_in_terminal() -> None:
            async with in_terminal():
                result = await history.app.run_async()
                if result is not None:
                    self.default_buffer.text = result

                app.vi_state.input_mode = InputMode.INSERT

        asyncio.ensure_future(do_in_terminal())

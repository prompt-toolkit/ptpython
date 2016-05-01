"""
CommandLineInterface for reading Python input.
This can be used for creation of Python REPLs.

::

    cli = PythonCommandLineInterface()
    cli.run()
"""
from __future__ import unicode_literals

from prompt_toolkit import AbortAction
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory, ConditionalAutoSuggest
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER, EditingMode
from prompt_toolkit.filters import Condition, Always
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.interface import CommandLineInterface, Application, AcceptAction
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import create_output
from prompt_toolkit.styles import DynamicStyle
from prompt_toolkit.utils import is_windows
from prompt_toolkit.validation import ConditionalValidator

from .completer import PythonCompleter
from .history_browser import create_history_application
from .key_bindings import load_python_bindings, load_sidebar_bindings, load_confirm_exit_bindings
from .layout import create_layout, CompletionVisualisation
from .prompt_style import IPythonPrompt, ClassicPrompt
from .style import get_all_code_styles, get_all_ui_styles, generate_style
from .utils import get_jedi_script_from_document, document_is_multiline_python
from .validator import PythonValidator

from functools import partial

import six
import __future__

if six.PY2:
    from pygments.lexers import PythonLexer
else:
    from pygments.lexers import Python3Lexer as PythonLexer

__all__ = (
    'PythonInput',
    'PythonCommandLineInterface',
)


class OptionCategory(object):
    def __init__(self, title, options):
        assert isinstance(title, six.text_type)
        assert isinstance(options, list)

        self.title = title
        self.options = options


class Option(object):
    """
    Ptpython configuration option that can be shown and modified from the
    sidebar.

    :param title: Text.
    :param description: Text.
    :param get_values: Callable that returns a dictionary mapping the
            possible values to callbacks that activate these value.
    :param get_current_value: Callable that returns the current, active value.
    """
    def __init__(self, title, description, get_current_value, get_values):
        assert isinstance(title, six.text_type)
        assert isinstance(description, six.text_type)
        assert callable(get_current_value)
        assert callable(get_values)

        self.title = title
        self.description = description
        self.get_current_value = get_current_value
        self.get_values = get_values

    @property
    def values(self):
        return self.get_values()

    def activate_next(self, _previous=False):
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

    def activate_previous(self):
        """
        Activate previous value.
        """
        self.activate_next(_previous=True)


class PythonInput(object):
    """
    Prompt for reading Python input.

    ::

        python_input = PythonInput(...)
        application = python_input.create_application()
        cli = PythonCommandLineInterface(application=application)
        python_code = cli.run()
    """
    def __init__(self,
                 get_globals=None, get_locals=None, history_filename=None,
                 vi_mode=False,

                 # For internal use.
                 _completer=None, _validator=None,
                 _lexer=None, _extra_buffers=None, _extra_buffer_processors=None,
                 _on_start=None,
                 _extra_layout_body=None, _extra_toolbars=None,
                 _input_buffer_height=None,
                 _accept_action=AcceptAction.RETURN_DOCUMENT,
                 _on_exit=AbortAction.RAISE_EXCEPTION):

        self.get_globals = get_globals or (lambda: {})
        self.get_locals = get_locals or self.get_globals

        self._completer = _completer or PythonCompleter(self.get_globals, self.get_locals)
        self._validator = _validator or PythonValidator(self.get_compiler_flags)
        self.history = FileHistory(history_filename) if history_filename else InMemoryHistory()
        self._lexer = _lexer or PygmentsLexer(PythonLexer)
        self._extra_buffers = _extra_buffers
        self._accept_action = _accept_action
        self._on_exit = _on_exit
        self._on_start = _on_start

        self._input_buffer_height = _input_buffer_height
        self._extra_layout_body = _extra_layout_body or []
        self._extra_toolbars = _extra_toolbars or []
        self._extra_buffer_processors = _extra_buffer_processors or []

        # Settings.
        self.show_signature = False
        self.show_docstring = False
        self.show_meta_enter_message = True
        self.completion_visualisation = CompletionVisualisation.MULTI_COLUMN
        self.completion_menu_scroll_offset = 1

        self.show_line_numbers = False
        self.show_status_bar = True
        self.wrap_lines = True
        self.complete_while_typing = True
        self.vi_mode = vi_mode
        self.paste_mode = False  # When True, don't insert whitespace after newline.
        self.confirm_exit = True  # Ask for confirmation when Control-D is pressed.
        self.accept_input_on_enter = 2  # Accept when pressing Enter 'n' times.
                                        # 'None' means that meta-enter is always required.
        self.enable_open_in_editor = True
        self.enable_system_bindings = True
        self.enable_input_validation = True
        self.enable_auto_suggest = False
        self.enable_mouse_support = False
        self.enable_history_search = False  # When True, like readline, going
                                            # back in history will filter the
                                            # history on the records starting
                                            # with the current input.

        self.highlight_matching_parenthesis = False
        self.show_sidebar = False  # Currently show the sidebar.
        self.show_sidebar_help = True # When the sidebar is visible, also show the help text.
        self.show_exit_confirmation = False  # Currently show 'Do you really want to exit?'
        self.terminal_title = None  # The title to be displayed in the terminal. (None or string.)
        self.exit_message = 'Do you really want to exit?'
        self.insert_blank_line_after_output = True  # (For the REPL.)

        # Tokens to be shown at the prompt.
        self.prompt_style = 'classic'  # The currently active style.

        self.all_prompt_styles = {  # Styles selectable from the menu.
            'ipython': IPythonPrompt(self),
            'classic': ClassicPrompt(),
        }

        self.get_input_prompt_tokens = lambda cli: \
            self.all_prompt_styles[self.prompt_style].in_tokens(cli)

        self.get_output_prompt_tokens = lambda cli: \
            self.all_prompt_styles[self.prompt_style].out_tokens(cli)

        #: Load styles.
        self.code_styles = get_all_code_styles()
        self.ui_styles = get_all_ui_styles()
        self._current_code_style_name = 'default'
        self._current_ui_style_name = 'default'

        if is_windows():
            self._current_code_style_name = 'win32'

        self._current_style = self._generate_style()
        self.true_color = False

        # Options to be configurable from the sidebar.
        self.options = self._create_options()
        self.selected_option_index = 0

        #: Incremeting integer counting the current statement.
        self.current_statement_index = 1

        # Code signatures. (This is set asynchronously after a timeout.)
        self.signatures = []

        # Use a KeyBindingManager for loading the key bindings.
        self.key_bindings_manager = KeyBindingManager(
            enable_abort_and_exit_bindings=True,
            enable_search=True,
            enable_vi_mode=Condition(lambda cli: self.vi_mode),
            enable_open_in_editor=Condition(lambda cli: self.enable_open_in_editor),
            enable_system_bindings=Condition(lambda cli: self.enable_system_bindings),
            enable_auto_suggest_bindings=Condition(lambda cli: self.enable_auto_suggest),

            # Disable all default key bindings when the sidebar or the exit confirmation
            # are shown.
            enable_all=Condition(lambda cli: not (self.show_sidebar or self.show_exit_confirmation)))

        load_python_bindings(self.key_bindings_manager, self)
        load_sidebar_bindings(self.key_bindings_manager, self)
        load_confirm_exit_bindings(self.key_bindings_manager, self)

        # Boolean indicating whether we have a signatures thread running.
        # (Never run more than one at the same time.)
        self._get_signatures_thread_running = False

    @property
    def option_count(self):
        " Return the total amount of options. (In all categories together.) "
        return sum(len(category.options) for category in self.options)

    @property
    def selected_option(self):
        " Return the currently selected option. "
        i = 0
        for category in self.options:
            for o in category.options:
                if i == self.selected_option_index:
                    return o
                else:
                    i += 1

    def get_compiler_flags(self):
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
    def key_bindings_registry(self):
        return self.key_bindings_manager.registry

    @property
    def add_key_binding(self):
        """
        Shortcut for adding new key bindings.
        (Mostly useful for a .ptpython/config.py file, that receives
        a PythonInput/Repl instance as input.)

        ::

            @python_input.add_key_binding(Keys.ControlX, filter=...)
            def handler(event):
                ...
        """
        # Extra key bindings should not be active when the sidebar is visible.
        sidebar_visible = Condition(lambda cli: self.show_sidebar)

        def add_binding_decorator(*keys, **kw):
            # Pop default filter keyword argument.
            filter = kw.pop('filter', Always())
            assert not kw

            return self.key_bindings_registry.add_binding(*keys, filter=filter & ~sidebar_visible)
        return add_binding_decorator

    def install_code_colorscheme(self, name, style_dict):
        """
        Install a new code color scheme.
        """
        assert isinstance(name, six.text_type)
        assert isinstance(style_dict, dict)

        self.code_styles[name] = style_dict

    def use_code_colorscheme(self, name):
        """
        Apply new colorscheme. (By name.)
        """
        assert name in self.code_styles

        self._current_code_style_name = name
        self._current_style = self._generate_style()

    def install_ui_colorscheme(self, name, style_dict):
        """
        Install a new UI color scheme.
        """
        assert isinstance(name, six.text_type)
        assert isinstance(style_dict, dict)

        self.ui_styles[name] = style_dict

    def use_ui_colorscheme(self, name):
        """
        Apply new colorscheme. (By name.)
        """
        assert name in self.ui_styles

        self._current_ui_style_name = name
        self._current_style = self._generate_style()

    def _generate_style(self):
        """
        Create new Style instance.
        (We don't want to do this on every key press, because each time the
        renderer receives a new style class, he will redraw everything.)
        """
        return generate_style(self.code_styles[self._current_code_style_name],
                              self.ui_styles[self._current_ui_style_name])

    def _create_options(self):
        """
        Create a list of `Option` instances for the options sidebar.
        """
        def enable(attribute, value=True):
            setattr(self, attribute, value)

            # Return `True`, to be able to chain this in the lambdas below.
            return True

        def disable(attribute):
            setattr(self, attribute, False)
            return True

        def simple_option(title, description, field_name, values=None):
            " Create Simple on/of option. "
            values = values or ['off', 'on']

            def get_current_value():
                return values[bool(getattr(self, field_name))]

            def get_values():
                return {
                    values[1]: lambda: enable(field_name),
                    values[0]: lambda: disable(field_name),
                }

            return Option(title=title, description=description,
                          get_values=get_values,
                          get_current_value=get_current_value)

        return [
            OptionCategory('Input', [
                simple_option(title='Input mode',
                              description='Vi or emacs key bindings.',
                              field_name='vi_mode',
                              values=['emacs', 'vi']),
                simple_option(title='Paste mode',
                              description="When enabled, don't indent automatically.",
                              field_name='paste_mode'),
                Option(title='Complete while typing',
                       description="Generate autocompletions automatically while typing. "
                                   'Don\'t require pressing TAB. (Not compatible with "History search".)',
                       get_current_value=lambda: ['off', 'on'][self.complete_while_typing],
                       get_values=lambda: {
                           'on': lambda: enable('complete_while_typing') and disable('enable_history_search'),
                           'off': lambda: disable('complete_while_typing'),
                       }),
                Option(title='History search',
                       description='When pressing the up-arrow, filter the history on input starting '
                                   'with the current text. (Not compatible with "Complete while typing".)',
                       get_current_value=lambda: ['off', 'on'][self.enable_history_search],
                       get_values=lambda: {
                           'on': lambda: enable('enable_history_search') and disable('complete_while_typing'),
                           'off': lambda: disable('enable_history_search'),
                       }),
                simple_option(title='Mouse support',
                              description='Respond to mouse clicks and scrolling for positioning the cursor, '
                                          'selecting text and scrolling through windows.',
                              field_name='enable_mouse_support'),
                simple_option(title='Confirm on exit',
                              description='Require confirmation when exiting.',
                              field_name='confirm_exit'),
                simple_option(title='Input validation',
                              description='In case of syntax errors, move the cursor to the error '
                                          'instead of showing a traceback of a SyntaxError.',
                              field_name='enable_input_validation'),
                simple_option(title='Auto suggestion',
                              description='Auto suggest inputs by looking at the history. '
                                          'Pressing right arrow or Ctrl-E will complete the entry.',
                              field_name='enable_auto_suggest'),
                Option(title='Accept input on enter',
                       description='Amount of ENTER presses required to execute input when the cursor '
                                   'is at the end of the input. (Note that META+ENTER will always execute.)',
                       get_current_value=lambda: str(self.accept_input_on_enter or 'meta-enter'),
                       get_values=lambda: {
                           '2': lambda: enable('accept_input_on_enter', 2),
                           '3': lambda: enable('accept_input_on_enter', 3),
                           '4': lambda: enable('accept_input_on_enter', 4),
                           'meta-enter': lambda: enable('accept_input_on_enter', None),
                       }),
            ]),
            OptionCategory('Display', [
                Option(title='Completions',
                       description='Visualisation to use for displaying the completions. (Multiple columns, one column, a toolbar or nothing.)',
                       get_current_value=lambda: self.completion_visualisation,
                       get_values=lambda: {
                           CompletionVisualisation.NONE: lambda: enable('completion_visualisation', CompletionVisualisation.NONE),
                           CompletionVisualisation.POP_UP: lambda: enable('completion_visualisation', CompletionVisualisation.POP_UP),
                           CompletionVisualisation.MULTI_COLUMN: lambda: enable('completion_visualisation', CompletionVisualisation.MULTI_COLUMN),
                           CompletionVisualisation.TOOLBAR: lambda: enable('completion_visualisation', CompletionVisualisation.TOOLBAR),
                       }),
                Option(title='Prompt',
                       description="Visualisation of the prompt. ('>>>' or 'In [1]:')",
                       get_current_value=lambda: self.prompt_style,
                       get_values=lambda: dict((s, partial(enable, 'prompt_style', s)) for s in self.all_prompt_styles)),
                simple_option(title='Blank line after output',
                              description='Insert a blank line after the output.',
                              field_name='insert_blank_line_after_output'),
                simple_option(title='Show signature',
                              description='Display function signatures.',
                              field_name='show_signature'),
                simple_option(title='Show docstring',
                              description='Display function docstrings.',
                              field_name='show_docstring'),
                simple_option(title='Show line numbers',
                              description='Show line numbers when the input consists of multiple lines.',
                              field_name='show_line_numbers'),
                simple_option(title='Show Meta+Enter message',
                              description='Show the [Meta+Enter] message when this key combination is required to execute commands. ' +
                                  '(This is the case when a simple [Enter] key press will insert a newline.',
                              field_name='show_meta_enter_message'),
                simple_option(title='Wrap lines',
                              description='Wrap lines instead of scrolling horizontally.',
                              field_name='wrap_lines'),
                simple_option(title='Show status bar',
                              description='Show the status bar at the bottom of the terminal.',
                              field_name='show_status_bar'),
                simple_option(title='Show sidebar help',
                              description='When the sidebar is visible, also show this help text.',
                              field_name='show_sidebar_help'),
                simple_option(title='Highlight parenthesis',
                              description='Highlight matching parenthesis, when the cursor is on or right after one.',
                              field_name='highlight_matching_parenthesis'),
            ]),
            OptionCategory('Colors', [
                Option(title='Code',
                       description='Color scheme to use for the Python code.',
                       get_current_value=lambda: self._current_code_style_name,
                       get_values=lambda: dict(
                            (name, partial(self.use_code_colorscheme, name)) for name in self.code_styles)
                       ),
                Option(title='User interface',
                       description='Color scheme to use for the user interface.',
                       get_current_value=lambda: self._current_ui_style_name,
                       get_values=lambda: dict(
                            (name, partial(self.use_ui_colorscheme, name)) for name in self.ui_styles)
                       ),
                simple_option(title='True color (24 bit)',
                              description='Use 24 bit colors instead of 265 colors',
                              field_name='true_color'),
            ]),
        ]

    def create_application(self):
        """
        Create an `Application` instance for use in a `CommandLineInterface`.
        """
        buffers = {
            'docstring': Buffer(read_only=True),
        }
        buffers.update(self._extra_buffers or {})

        return Application(
            layout=create_layout(
                self,
                self.key_bindings_manager,
                lexer=self._lexer,
                input_buffer_height=self._input_buffer_height,
                extra_buffer_processors=self._extra_buffer_processors,
                extra_body=self._extra_layout_body,
                extra_toolbars=self._extra_toolbars),
            buffer=self._create_buffer(),
            buffers=buffers,
            key_bindings_registry=self.key_bindings_registry,
            paste_mode=Condition(lambda cli: self.paste_mode),
            mouse_support=Condition(lambda cli: self.enable_mouse_support),
            on_abort=AbortAction.RETRY,
            on_exit=self._on_exit,
            style=DynamicStyle(lambda: self._current_style),
            get_title=lambda: self.terminal_title,
            on_initialize=self._on_cli_initialize,
            on_start=self._on_start,
            on_input_timeout=self._on_input_timeout)

    def _create_buffer(self):
        """
        Create the `Buffer` for the Python input.
        """
        def is_buffer_multiline():
            return (self.paste_mode or
                    self.accept_input_on_enter is None or
                    document_is_multiline_python(python_buffer.document))

        python_buffer = Buffer(
            is_multiline=Condition(is_buffer_multiline),
            complete_while_typing=Condition(lambda: self.complete_while_typing),
            enable_history_search=Condition(lambda: self.enable_history_search),
            tempfile_suffix='.py',
            history=self.history,
            completer=self._completer,
            validator=ConditionalValidator(
                self._validator,
                Condition(lambda: self.enable_input_validation)),
            auto_suggest=ConditionalAutoSuggest(
                AutoSuggestFromHistory(),
                Condition(lambda cli: self.enable_auto_suggest)),
            accept_action=self._accept_action)

        return python_buffer

    def _on_cli_initialize(self, cli):
        """
        Called when a CommandLineInterface has been created.
        """
        # Synchronize PythonInput state with the CommandLineInterface.
        def synchronize(_=None):
            if self.vi_mode:
                cli.editing_mode = EditingMode.VI
            else:
                cli.editing_mode = EditingMode.EMACS

        cli.input_processor.beforeKeyPress += synchronize
        cli.input_processor.afterKeyPress += synchronize
        synchronize()

    def _on_input_timeout(self, cli):
        """
        When there is no input activity,
        in another thread, get the signature of the current code.
        """
        if cli.current_buffer_name != DEFAULT_BUFFER:
            return

        # Never run multiple get-signature threads.
        if self._get_signatures_thread_running:
            return
        self._get_signatures_thread_running = True

        buffer = cli.current_buffer
        document = buffer.document

        def run():
            script = get_jedi_script_from_document(document, self.get_locals(), self.get_globals())

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
            if buffer.text == document.text:
                self.signatures = signatures

                # Set docstring in docstring buffer.
                if signatures:
                    string = signatures[0].docstring()
                    if not isinstance(string, six.text_type):
                        string = string.decode('utf-8')
                    cli.buffers['docstring'].reset(
                        initial_document=Document(string, cursor_position=0))
                else:
                    cli.buffers['docstring'].reset()

                cli.request_redraw()
            else:
                self._on_input_timeout(cli)

        cli.eventloop.run_in_executor(run)

    def on_reset(self, cli):
        self.key_bindings_manager.reset(cli)
        self.signatures = []

    def enter_history(self, cli):
        """
        Display the history.
        """
        cli.vi_state.input_mode = InputMode.NAVIGATION

        def done(result):
            if result is not None:
                cli.buffers[DEFAULT_BUFFER].document = result

            cli.vi_state.input_mode = InputMode.INSERT

        cli.run_sub_application(create_history_application(
            self, cli.buffers[DEFAULT_BUFFER].document), done)


class PythonCommandLineInterface(CommandLineInterface):
    def __init__(self, eventloop=None, python_input=None, input=None, output=None):
        assert python_input is None or isinstance(python_input, PythonInput)

        python_input = python_input or PythonInput()

        # Make sure that the prompt_toolkit 'renderer' knows about the
        # 'true_color' property of PythonInput.
        if output is None:
            output=create_output(true_color=Condition(lambda: python_input.true_color))

        super(PythonCommandLineInterface, self).__init__(
            application=python_input.create_application(),
            eventloop=eventloop,
            input=input,
            output=output)

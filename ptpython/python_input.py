"""
CommandLineInterface for reading Python input.
This can be used for creation of Python REPLs.

::

    cli = PythonCommandLineInterface()
    cli.run()
"""
from __future__ import unicode_literals

from prompt_toolkit import AbortAction
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition, Always
from prompt_toolkit.history import FileHistory, History
from prompt_toolkit.interface import CommandLineInterface, Application, AcceptAction
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.utils import Callback

from ptpython.completer import PythonCompleter
from ptpython.key_bindings import load_python_bindings, load_sidebar_bindings
from ptpython.layout import PythonPrompt, create_layout
from ptpython.style import get_all_code_styles, get_all_ui_styles, generate_style
from ptpython.utils import get_jedi_script_from_document, document_is_multiline_python
from ptpython.validator import PythonValidator

from pygments.lexers import PythonLexer
from functools import partial

import six


__all__ = (
    'PythonInput',
    'PythonCommandLineInterface',
)

class _Option(object):
    """
    Ptpython configuration option that can be shown and modified from the
    sidebar.

    :param description: Text.
    :param get_values: Callable that returns a dictionary mapping the
            possible values to callbacks that activate these value.
    :param get_current_value: Callable that returns the current, active value.
    """
    def __init__(self, description, get_values, get_current_value):
        assert isinstance(description, six.text_type)
        assert callable(get_values)
        assert callable(get_current_value)

        self.description = description
        self.get_values = get_values
        self.get_current_value = get_current_value

    @property
    def values(self):
        return self.get_values()

    def activate_next(self, _previous=False):
        """
        Activate next value.
        """
        current = self.get_current_value()
        options = sorted(self.values.keys())

        if _previous:
            next_option = options[(options.index(current) - 1) % len(options)]
        else:
            next_option = options[(options.index(current) + 1) % len(options)]

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
        cli = CommandLineInterface(application=application)
        python_code = cli.run()
    """
    def __init__(self,
                 get_globals=None, get_locals=None, history_filename=None,
                 vi_mode=False,

                 # For internal use.
                 _completer=None, _validator=None, _python_prompt_control=None,
                 _lexer=None, _extra_buffers=None, _extra_buffer_processors=None,
                 _on_start=None,
                 _extra_sidebars=None,
                 _accept_action=AcceptAction.RETURN_DOCUMENT,
                 _on_exit=AbortAction.RAISE_EXCEPTION):

        self.get_globals = get_globals or (lambda: {})
        self.get_locals = get_locals or self.get_globals

        self._completer = _completer or PythonCompleter(self.get_globals, self.get_locals)
        self._validator = _validator or PythonValidator()
        self._history = FileHistory(history_filename) if history_filename else History()
        self._lexer = _lexer or PythonLexer
        self._extra_buffers = _extra_buffers
        self._accept_action = _accept_action
        self._on_exit = _on_exit
        self._on_start = _on_start

        self._extra_sidebars = _extra_sidebars or []
        self._extra_buffer_processors = _extra_buffer_processors or []

        self._python_prompt_control = _python_prompt_control or PythonPrompt(self)

        # Settings.
        self.show_sidebar = False
        self.show_signature = True
        self.show_docstring = False
        self.show_completions_toolbar = False
        self.show_completions_menu = True
        self.show_line_numbers = True
        self.show_status_bar = True
        self.complete_while_typing = True
        self.vi_mode = vi_mode
        self.paste_mode = False  # When True, don't insert whitespace after newline.
        self.enable_open_in_editor = True
        self.enable_system_bindings = True
        self.enable_history_search = False  # When True, like readline, going
                                            # back in history will filter the
                                            # history on the records starting
                                            # with the current input.

        #: Load styles.
        self.code_styles = get_all_code_styles()
        self.ui_styles = get_all_ui_styles()
        self._current_code_style_name = 'default'
        self._current_ui_style_name = 'default'
        self._current_style = self._generate_style()

        # Options to be configurable from the sidebar.
        def handler(enable=None, disable=None):
            " Handler for an '_Option'. "
            def handler():
                if enable:
                    for o in enable:
                        setattr(self, o, True)

                if disable:
                    for o in disable:
                        setattr(self, o, False)
            return handler

        def simple_option(description, field_name, values=None):
            " Create Simple on/of option. "
            values = values or ['off', 'on']

            def current_value():
                return values[bool(getattr(self, field_name))]

            return _Option(description, lambda: {
                values[1]: handler(enable=[field_name]),
                values[0]: handler(disable=[field_name]),
            }, current_value)

        def get_completion_menu_value():
            " Return active value for the 'completion menu' option. "
            if self.show_completions_menu:
                return 'pop-up'
            elif self.show_completions_toolbar:
                return 'toolbar'
            else:
                return 'off'

        self.options = [
            simple_option('Input mode', 'vi_mode', values=['emacs', 'vi']),
            simple_option('Paste mode', 'paste_mode'),
            _Option('Completion menu', lambda: {
                'off': handler(disable=['show_completions_menu', 'show_completions_toolbar']),
                'pop-up': handler(enable=['show_completions_menu'],
                                  disable=['show_completions_toolbar']),
                'toolbar': handler(enable=['show_completions_toolbar'],
                                  disable=['show_completions_menu'])
            }, get_completion_menu_value),
            _Option('Complete while typing', lambda: {
                'on': handler(enable=['complete_while_typing'], disable=['enable_history_search']),
                'off': handler(disable=['complete_while_typing']),
            }, lambda: ['off', 'on'][self.complete_while_typing]),
            simple_option('Show signature', 'show_signature'),
            simple_option('Show docstring', 'show_docstring'),
            simple_option('Show line numbers', 'show_line_numbers'),
            simple_option('Show status bar', 'show_status_bar'),
            _Option('History search', lambda: {
                'on': handler(enable=['enable_history_search'], disable=['complete_while_typing']),
                'off': handler(disable=['enable_history_search']),
            }, lambda: ['off', 'on'][self.enable_history_search]),
            _Option('Color scheme (code)', lambda: {
                name: partial(self.use_code_colorscheme, name) for name in self.code_styles
            }, lambda: self._current_code_style_name),
            _Option('Color scheme (UI)', lambda: {
                name: partial(self.use_ui_colorscheme, name) for name in self.ui_styles
            }, lambda: self._current_ui_style_name),
        ]
        self.selected_option = 0

        #: Incremeting integer counting the current statement.
        self.current_statement_index = 1

        # Code signatures. (This is set asynchronously after a timeout.)
        self.signatures = []

        # Use a KeyBindingManager for loading the key bindings.
        self.key_bindings_manager = KeyBindingManager(
            enable_vi_mode=Condition(lambda cli: self.vi_mode),
            enable_open_in_editor=Condition(lambda cli: self.enable_open_in_editor),
            enable_system_bindings=Condition(lambda cli: self.enable_system_bindings),
            enable_all=Condition(lambda cli: not self.show_sidebar))

        load_python_bindings(self.key_bindings_manager, self)
        load_sidebar_bindings(self.key_bindings_manager, self)

        # Boolean indicating whether we have a signatures thread running.
        # (Never run more than one at the same time.)
        self._get_signatures_thread_running = False

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

    def create_application(self):
        """
        Create an `Application` instance for use in a `CommandLineInterface`.
        """
        buffers = {
            'docstring': Buffer(),  # XXX: make docstring read only.
        }
        buffers.update(self._extra_buffers or {})

        return Application(
            layout=create_layout(
                self,
                self.key_bindings_manager, self._python_prompt_control,
                lexer=self._lexer,
                extra_buffer_processors=self._extra_buffer_processors,
                extra_sidebars=self._extra_sidebars),
            buffer=self._create_buffer(),
            buffers=buffers,
            key_bindings_registry=self.key_bindings_registry,
            paste_mode=Condition(lambda cli: self.paste_mode),
            on_abort=AbortAction.RETRY,
            on_exit=self._on_exit,
            get_style=lambda: self._current_style,
            on_start=self._on_start,
            on_input_timeout=Callback(self._on_input_timeout))

    def _create_buffer(self):
        """
        Create the `Buffer` for the Python input.
        """
        def is_buffer_multiline():
            return (self.paste_mode or
                    document_is_multiline_python(python_buffer.document))

        python_buffer = Buffer(
            is_multiline=Condition(is_buffer_multiline),
            complete_while_typing=Condition(lambda: self.complete_while_typing),
            enable_history_search=Condition(lambda: self.enable_history_search),
            tempfile_suffix='.py',
            history=self._history,
            completer=self._completer,
            validator=self._validator,
            accept_action=self._accept_action)

        return python_buffer

    def _on_input_timeout(self, cli):
        """
        When there is no input activity,
        in another thread, get the signature of the current code.
        """
        if cli.focus_stack.current != DEFAULT_BUFFER:
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
        self.key_bindings_manager.reset()
        self.signatures = []


class PythonCommandLineInterface(CommandLineInterface):
    def __init__(self, eventloop=None, input=None, output=None):
        python_input = PythonInput()

        super(PythonCommandLineInterface, self).__init__(
            application=python_input.create_application(),
            eventloop=eventloop,
            input=input,
            output=output)

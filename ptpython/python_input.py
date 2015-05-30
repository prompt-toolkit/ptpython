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
from prompt_toolkit.filters import Condition, Always
from prompt_toolkit.history import FileHistory, History
from prompt_toolkit.interface import CommandLineInterface, Application, AcceptAction
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.utils import Callback

from ptpython.completer import PythonCompleter
from ptpython.key_bindings import load_python_bindings
from ptpython.layout import PythonPrompt, create_layout
from ptpython.style import PythonStyle
from ptpython.utils import get_jedi_script_from_document, document_is_multiline_python
from ptpython.validator import PythonValidator

from pygments.lexers import PythonLexer

import six

__all__ = (
    'PythonInput',
    'PythonCommandLineInterface',
)


class PythonInput(object):
    """
    `Application` for Python input.
    """
    def __init__(self,
                 get_globals=None, get_locals=None, history_filename=None,
                 vi_mode=False, style=PythonStyle,

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
        self._style = style
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
        self.complete_while_typing = True
        self.vi_mode = vi_mode
        self.paste_mode = False  # When True, don't insert whitespace after newline.

        #: Incremeting integer counting the current statement.
        self.current_statement_index = 1

        # Code signatures. (This is set asynchronously after a timeout.)
        self.signatures = []

        # Use a KeyBindingManager for loading the key bindings.
        self._key_bindings_manager = KeyBindingManager(
            enable_vi_mode=Condition(lambda cli: self.vi_mode),
            enable_open_in_editor=Always(),
            enable_system_prompt=Always())
        load_python_bindings(self._key_bindings_manager, self)

        # Boolean indicating whether we have a signatures thread running.
        # (Never run more than one at the same time.)
        self._get_signatures_thread_running = False

    def create_application(self):
        buffers = {
            'docstring': Buffer(),  # XXX: make docstring read only.
        }
        buffers.update(self._extra_buffers or {})

        return Application(
            layout=create_layout(
                self,
                self._key_bindings_manager, self._python_prompt_control,
                lexer=self._lexer,
                extra_buffer_processors=self._extra_buffer_processors,
                extra_sidebars=self._extra_sidebars),
            buffer=self._create_buffer(),
            buffers=buffers,
            key_bindings_registry=self._key_bindings_manager.registry,
            paste_mode=Condition(lambda cli: self.paste_mode),
            on_abort=AbortAction.RETRY,
            on_exit=self._on_exit,
            style=self._style,
            on_start=self._on_start,
            on_input_timeout=Callback(self._on_input_timeout))

    def _create_buffer(self):
        def is_buffer_multiline():
            return (self.paste_mode or
                    document_is_multiline_python(python_buffer.document))

        python_buffer = Buffer(
            is_multiline=Condition(is_buffer_multiline),
            complete_while_typing=Condition(lambda: self.complete_while_typing),
            enable_history_search=Always(),
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
        if cli.focus_stack.current != 'default':
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
        self._key_bindings_manager.reset()
        self.signatures = []


class PythonCommandLineInterface(CommandLineInterface):
    def __init__(self, eventloop=None, input=None, output=None):
        python_input = PythonInput()

        super(PythonCommandLineInterface, self).__init__(
            application=python_input.create_application(),
            eventloop=eventloop,
            input=input,
            output=output)

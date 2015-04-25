"""
CommandLineInterface for reading Python input.
This can be used for creation of Python REPLs.

::

    from prompt_toolkit.contrib.python_import import PythonCommandLineInterface

    python_interface = PythonCommandLineInterface()
    python_interface.cli.read_input()
"""
from __future__ import unicode_literals

from prompt_toolkit import AbortAction
from prompt_toolkit import CommandLineInterface
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition, Always
from prompt_toolkit.history import FileHistory, History
from prompt_toolkit.key_binding.manager import KeyBindingManager

from ptpython.completer import PythonCompleter
from ptpython.key_bindings import load_python_bindings
from ptpython.layout import PythonPrompt, create_layout
from ptpython.style import PythonStyle
from ptpython.utils import get_jedi_script_from_document, document_is_multiline_python
from ptpython.validator import PythonValidator

from pygments.lexers import PythonLexer

import six

__all__ = (
    'PythonCommandLineInterface',
)


class PythonCLISettings(object):
    """
    Settings for the Python REPL which can change at runtime.
    """
    def __init__(self, paste_mode=False):
        self.show_sidebar = False
        self.show_signature = True
        self.show_docstring = False
        self.show_completions_toolbar = False
        self.show_completions_menu = True
        self.show_line_numbers = True
        self.complete_while_typing = True

        #: Boolean `paste` flag. If True, don't insert whitespace after a
        #: newline.
        self.paste_mode = paste_mode

        #: Incremeting integer counting the current statement.
        self.current_statement_index = 1

        # Code signatures. (This is set asynchronously after a timeout.)
        self.signatures = []


class PythonCommandLineInterface(object):
    def __init__(self,
                 eventloop,
                 get_globals=None, get_locals=None,
                 stdin=None, stdout=None,
                 vi_mode=False, history_filename=None,
                 style=PythonStyle,

                 # For internal use.
                 _completer=None,
                 _validator=None,
                 _lexer=None,
                 _python_prompt_control=None,
                 _extra_buffers=None,
                 _extra_buffer_processors=None,
                 _extra_sidebars=None):

        self.settings = PythonCLISettings()

        self.get_globals = get_globals or (lambda: {})
        self.get_locals = get_locals or self.get_globals

        self.completer = _completer or PythonCompleter(self.get_globals, self.get_locals)
        self.validator = _validator or PythonValidator()
        self.history = FileHistory(history_filename) if history_filename else History()
        self.python_prompt_control = _python_prompt_control or PythonPrompt(self.settings)
        self._extra_sidebars = _extra_sidebars or []
        self._extra_buffer_processors = _extra_buffer_processors or []
        self._lexer = _lexer or PythonLexer

        # Use a KeyBindingManager for loading the key bindings.
        self.key_bindings_manager = KeyBindingManager(enable_vi_mode=vi_mode,
                                                      enable_open_in_editor=True,
                                                      enable_system_prompt=True)
        load_python_bindings(self.key_bindings_manager, self.settings)

        self.get_signatures_thread_running = False

        buffers = {
            'default': self._create_python_buffer(),
            'docstring': Buffer(), # XXX: make docstring read only.
        }
        buffers.update(_extra_buffers or {})

        self.cli = CommandLineInterface(
            eventloop=eventloop,
            style=style,
            key_bindings_registry=self.key_bindings_manager.registry,
            buffers=buffers,
            paste_mode=Condition(lambda cli: self.settings.paste_mode),
            layout=self._create_layout(),
            on_abort=AbortAction.RETRY,
            on_exit=AbortAction.RAISE_EXCEPTION)

        def on_input_timeout():
            """
            When there is no input activity,
            in another thread, get the signature of the current code.
            """
            if self.cli.focus_stack.current != 'default':
                return

            # Never run multiple get-signature threads.
            if self.get_signatures_thread_running:
                return
            self.get_signatures_thread_running = True

            buffer = self.cli.current_buffer
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

                self.get_signatures_thread_running = False

                # Set signatures and redraw if the text didn't change in the
                # meantime. Otherwise request new signatures.
                if buffer.text == document.text:
                    self.settings.signatures = signatures

                    # Set docstring in docstring buffer.
                    if signatures:
                        string = signatures[0].docstring()
                        if not isinstance(string, six.text_type):
                            string = string.decode('utf-8')
                        self.cli.buffers['docstring'].reset(
                            initial_document=Document(string, cursor_position=0))
                    else:
                        self.cli.buffers['docstring'].reset()

                    self.cli.request_redraw()
                else:
                    on_input_timeout()

            self.cli.eventloop.run_in_executor(run)

        def reset():
            self.key_bindings_manager.reset()
            self.settings.signatures = []
        self.cli.onReset += reset

        self.cli.onInputTimeout += on_input_timeout

    def _create_layout(self):
        """
        Generate new layout.
        """
        return create_layout(
            self.settings, self.key_bindings_manager, self.python_prompt_control,
            lexer=self._lexer,
            extra_buffer_processors=self._extra_buffer_processors,
            extra_sidebars=self._extra_sidebars)

    def _create_python_buffer(self):
        def is_buffer_multiline():
            return (self.settings.paste_mode or
                    document_is_multiline_python(b.document))

        b = Buffer(
            is_multiline=Condition(is_buffer_multiline),
            complete_while_typing=Condition(lambda: self.settings.complete_while_typing),
            enable_history_search=Always(),
            tempfile_suffix='.py',
            history=self.history,
            completer=self.completer,
            validator=self.validator)
        return b

"""
CommandLineInterface for reading Python input.
This can be used for creation of Python REPLs.

::

    from prompt_toolkit.contrib.python_import import PythonCommandLineInterface

    python_interface = PythonCommandLineInterface()
    python_interface.cli.read_input()
"""
from __future__ import unicode_literals

from prompt_toolkit import CommandLineInterface
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.history import FileHistory, History
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding.bindings.utils import focus_next_buffer
from prompt_toolkit.filters import AlwaysOff

from ptpython.completer import PythonCompleter
from ptpython.filters import HasSignature, ShowDocstring
from ptpython.key_bindings import load_python_bindings
from ptpython.layout import PythonPrompt, create_layout
from ptpython.style import PythonStyle
from ptpython.utils import current_python_buffer, get_jedi_script_from_document, document_is_multiline_python
from ptpython.validator import PythonValidator

import six

__all__ = (
    'PythonCommandLineInterface',
)


class PythonBuffer(Buffer):  # XXX: don't use inheritance.
    """
    Custom `Buffer` class with some helper functions.
    """
    def reset(self, *a, **kw):
        super(PythonBuffer, self).reset(*a, **kw)

        # Code signatures. (This is set asynchronously after a timeout.)
        self.signatures = []


class PythonCLISettings(object):
    """
    Settings for the Python REPL which can change at runtime.
    """
    def __init__(self, paste_mode=False):
        self.currently_multiline = False
        self.show_sidebar = False
        self.show_signature = True
        self.show_docstring = True
        self.show_completions_toolbar = False
        self.show_completions_menu = True
        self.show_line_numbers = True
        self.show_all_buffers = False  # split screen otherwise.

        #: Boolean `paste` flag. If True, don't insert whitespace after a
        #: newline.
        self.paste_mode = paste_mode

        #: Incremeting integer counting the current statement.
        self.current_statement_index = 1

        #: Incrementing for tab numbers
        self.buffer_index = 0


class PythonCommandLineInterface(object):
    def __init__(self,
                 get_globals=None, get_locals=None,
                 stdin=None, stdout=None,
                 vi_mode=False, history_filename=None,
                 style=PythonStyle,

                 # For internal use.
                 _completer=None,
                 _validator=None,
                 _python_prompt_control=None,
                 _extra_buffers=None,
                 _extra_sidebars=None):

        self.settings = PythonCLISettings()

        self.get_globals = get_globals or (lambda: {})
        self.get_locals = get_locals or self.get_globals

        self.completer = _completer or PythonCompleter(self.get_globals, self.get_locals)
        self.validator = _validator or PythonValidator()
        self.history = FileHistory(history_filename) if history_filename else History()
        self.python_prompt_control = _python_prompt_control or PythonPrompt(self.settings)
        self._extra_sidebars = _extra_sidebars or []

        # Use a KeyBindingManager for loading the key bindings.
        self.key_bindings_manager = KeyBindingManager(enable_vi_mode=vi_mode, enable_system_prompt=True)
        load_python_bindings(self.key_bindings_manager, self.settings,
                             add_buffer=self.add_new_python_buffer,
                             close_current_buffer=self.close_current_python_buffer)

        self.get_signatures_thread_running = False

        buffers = {
            'default': Buffer(focussable=AlwaysOff()),  # Never use or focus the default buffer.
            'docstring': Buffer(focussable=HasSignature(self.settings) & ShowDocstring(self.settings)),
                                # XXX: also make docstring read only.
        }
        buffers.update(_extra_buffers or {})

        self.cli = CommandLineInterface(
            style=style,
            key_bindings_registry=self.key_bindings_manager.registry,
            buffers=buffers,
            create_async_autocompleters=True)

        def on_input_timeout():
            """
            When there is no input activity,
            in another thread, get the signature of the current code.
            """
            if not self.cli.focus_stack.current.startswith('python-'):
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
                    buffer.signatures = signatures

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

            self.cli.run_in_executor(run)

        self.cli.onInputTimeout += on_input_timeout
        self.cli.onReset += self.key_bindings_manager.reset

        self.add_new_python_buffer()

    def _update_layout(self):
        """
        Generate new layout.
        (To be done when we add/remove buffers.)
        """
        self.cli.layout = create_layout(
            self.cli.buffers, self.settings, self.key_bindings_manager, self.python_prompt_control,
            extra_sidebars=self._extra_sidebars)

    def add_new_python_buffer(self):
        # Create a new buffer.
        buffer = self._create_buffer()
        self.settings.buffer_index += 1
        name = 'python-%i' % self.settings.buffer_index

        # Insert and update layout.
        self.cli.add_buffer(name, buffer, focus=True)
        self._update_layout()

    def close_current_python_buffer(self):
        name, _ = current_python_buffer(self.cli, self.settings)

        if name:
            python_buffers_left = len([b for b in self.cli.buffers if b.startswith('python-')])

            if python_buffers_left > 1:
                focus_next_buffer(self.cli, name_filter=lambda name: name.startswith('python-'))
                del self.cli.buffers[name]
                self._update_layout()
            else:
                self.cli.set_exit()

    def _create_buffer(self):
        def is_buffer_multiline(document):
            return (self.settings.paste_mode or
                    self.settings.currently_multiline or
                    document_is_multiline_python(document))

        return PythonBuffer(
            is_multiline=is_buffer_multiline,
            tempfile_suffix='.py',
            history=self.history,
            completer=self.completer,
            validator=self.validator)

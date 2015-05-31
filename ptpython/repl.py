"""
Utility for creating a Python repl.

::

    from ptpython.repl import embed
    embed(globals(), locals(), vi_mode=False)

"""
from __future__ import unicode_literals

from pygments import highlight
from pygments.formatters.terminal256 import Terminal256Formatter
from pygments.lexers import PythonTracebackLexer

from prompt_toolkit.application import AbortAction
from prompt_toolkit.utils import DummyContext, Callback
from prompt_toolkit.shortcuts import create_eventloop, create_asyncio_eventloop
from prompt_toolkit.interface import AcceptAction, CommandLineInterface

from .python_input import PythonStyle, PythonInput
from ._eval import eval_  # eval() without `unicode_literals` and `print_function`.

import os
import six
import sys
import traceback
import warnings

__all__ = (
    'PythonRepl',
    'enable_deprecation_warnings',
    'run_config',
    'embed',
)


class PythonRepl(PythonInput):
    def __init__(self, *a, **kw):
        self._startup_paths = kw.pop('startup_paths', None)

        kw.update({
            '_accept_action': AcceptAction.run_in_terminal(
                handler=self._process_document, render_cli_done=True),
            '_on_start': Callback(self._on_start),
            '_on_exit': AbortAction.RETURN_NONE,
        })

        super(PythonRepl, self).__init__(*a, **kw)

    def _on_start(self, cli):
        """
        Start the Read-Eval-Print Loop.
        """
        if self._startup_paths:
            for path in self._startup_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        code = compile(f.read(), path, 'exec')
                        six.exec_(code, self.get_globals(), self.get_locals())
                else:
                    output = self.cli.output
                    output.write('WARNING | File not found: {}\n\n'.format(path))

    def _process_document(self, cli, buffer):
        line = buffer.text

        if line and not line.isspace():
            try:
                # Eval and print.
                self._execute(cli, line)
            except KeyboardInterrupt as e:  # KeyboardInterrupt doesn't inherit from Exception.
                self._handle_keyboard_interrupt(cli, e)
            except Exception as e:
                self._handle_exception(cli, e)

            self.current_statement_index += 1
            self.signatures = []

            # Append to history and reset.
            cli.search_state.text = ''
            cli.buffers['default'].reset(append_to_history=True)
            self.key_bindings_manager.reset()

    def _execute(self, cli, line):
        """
        Evaluate the line and print the result.
        """
        output = cli.output

        if line[0:1] == '!':
            # Run as shell command
            os.system(line[1:])
        else:
            # Try eval first
            try:
                result = eval_(line, self.get_globals(), self.get_locals())
                locals = self.get_locals()
                locals['_'] = locals['_%i' % self.current_statement_index] = result

                if result is not None:
                    out_mark = 'Out[%i]: ' % self.current_statement_index

                    try:
                        result_str = '%r\n' % (result, )
                    except UnicodeDecodeError:
                        # In Python 2: `__repr__` should return a bytestring,
                        # so to put it in a unicode context could raise an
                        # exception that the 'ascii' codec can't decode certain
                        # characters. Decode as utf-8 in that case.
                        result_str = '%s\n' % repr(result).decode('utf-8')

                    # align every line to the first one
                    line_sep = '\n' + ' ' * len(out_mark)
                    out_string = out_mark + line_sep.join(result_str.splitlines())

                    output.write(out_string)
            # If not a valid `eval` expression, run using `exec` instead.
            except SyntaxError:
                six.exec_(line, self.get_globals(), self.get_locals())

            output.write('\n\n')
            output.flush()

    @classmethod
    def _handle_exception(cls, cli, e):
        output = cli.output

        # Instead of just calling ``traceback.format_exc``, we take the
        # traceback and skip the bottom calls of this framework.
        t, v, tb = sys.exc_info()
        tblist = traceback.extract_tb(tb)[3:]
        l = traceback.format_list(tblist)
        if l:
            l.insert(0, "Traceback (most recent call last):\n")
        l.extend(traceback.format_exception_only(t, v))
        tb = ''.join(l)

        # Format exception and write to output.
        output.write(highlight(tb, PythonTracebackLexer(), Terminal256Formatter()))
        output.write('%s\n\n' % e)
        output.flush()

    @classmethod
    def _handle_keyboard_interrupt(cls, cli, e):
        output = cli.output

        output.write('\rKeyboardInterrupt\n\n')
        output.flush()


def enable_deprecation_warnings():
    """
    Show deprecation warnings, when they are triggered directly by actions in
    the REPL. This is recommended to call, before calling `embed`.

    e.g. This will show an error message when the user imports the 'sha'
         library on Python 2.7.
    """
    warnings.filterwarnings('default', category=DeprecationWarning,
                            module='__main__')


def run_config(repl, config_file='~/.ptpython/config.py'):
    """
    Execute REPL config file.

    :param repl: `PythonInput` instance.
    :param config_file: Path of the configuration file.
    """
    assert isinstance(repl, PythonInput)
    assert isinstance(config_file, six.text_type)

    # Expand tildes.
    config_file = os.path.expanduser(config_file)

    def enter_to_continue():
         six.moves.input('\nPress ENTER to continue...')

    # Check whether this file exists.
    if not os.path.exists(config_file):
        print('Impossible to read %r' % config_file)
        enter_to_continue()
        return

    # Run the config file in an empty namespace.
    try:
        namespace = {}

        with open(config_file, 'r') as f:
            code = compile(f.read(), config_file, 'exec')
            six.exec_(code, namespace, namespace)

        # Now we should have a 'configure' method in this namespace. We call this
        # method with the repl as an argument.
        if 'configure' in namespace:
            namespace['configure'](repl)

    except Exception:
         traceback.print_exc()
         enter_to_continue()


def embed(globals=None, locals=None, configure=None,
          vi_mode=False, history_filename=None, no_colors=False,
          startup_paths=None, patch_stdout=False, return_asyncio_coroutine=False):
    """
    Call this to embed  Python shell at the current point in your program.
    It's similar to `IPython.embed` and `bpython.embed`. ::

        from prompt_toolkit.contrib.repl import embed
        embed(globals(), locals())

    :param vi_mode: Boolean. Use Vi instead of Emacs key bindings.
    :param configure: Callable that will be called with the `PythonRepl` as a first
                      argument, to trigger configuration.
    """
    assert configure is None or callable(configure)

    # Default globals/locals
    if globals is None:
        globals = {
            '__name__': '__main__',
            '__package__': None,
            '__doc__': None,
            '__builtins__': six.moves.builtins,
        }

    locals = locals or globals

    def get_globals():
        return globals

    def get_locals():
        return locals

    # Create eventloop.
    if return_asyncio_coroutine:
        eventloop = create_asyncio_eventloop()
    else:
        eventloop = create_eventloop()

    # Create REPL.
    repl = PythonRepl(get_globals, get_locals, vi_mode=vi_mode,
                      history_filename=history_filename,
                      style=(None if no_colors else PythonStyle),
                      startup_paths=startup_paths)

    if configure:
        configure(repl)

    cli = CommandLineInterface(application=repl.create_application(), eventloop=eventloop)

    # Start repl.
    patch_context = cli.patch_stdout_context() if patch_stdout else DummyContext()

    if return_asyncio_coroutine:
        def coroutine():
            with patch_context:
                for future in cli.run_async():
                    yield future
        return coroutine()
    else:
        with patch_context:
            cli.run()

"""
Utility for creating a Python repl.

::

    from ptpython.repl import embed
    embed(globals(), locals(), vi_mode=False)

"""
from __future__ import unicode_literals

from pygments.lexers import PythonTracebackLexer, PythonLexer
from pygments.styles.default import DefaultStyle

from prompt_toolkit.application import AbortAction
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.interface import AcceptAction
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.layout.utils import token_list_width
from prompt_toolkit.shortcuts import create_asyncio_eventloop
from prompt_toolkit.styles import style_from_pygments
from prompt_toolkit.utils import DummyContext

from .python_input import PythonInput, PythonCommandLineInterface
from .eventloop import create_eventloop

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
            '_on_start': self._on_start,
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
                    output = cli.output
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

            if self.insert_blank_line_after_output:
                cli.output.write('\n')

            self.current_statement_index += 1
            self.signatures = []

            # Append to history and reset.
            cli.search_state.text = ''
            cli.buffers[DEFAULT_BUFFER].reset(append_to_history=True)

        # Make sure that we end up in insert mode.
        # (Not exactly the right place to check this.)
        if cli.vi_state.input_mode == InputMode.NAVIGATION:
            cli.vi_state.input_mode = InputMode.INSERT

    def _execute(self, cli, line):
        """
        Evaluate the line and print the result.
        """
        output = cli.output

        def compile_with_flags(code, mode):
            " Compile code with the right compiler flags. "
            return compile(code, '<stdin>', mode,
                           flags=self.get_compiler_flags(),
                           dont_inherit=True)

        if line.lstrip().startswith('\x1a'):
            # When the input starts with Ctrl-Z, quit the REPL.
            cli.exit()

        elif line.lstrip().startswith('!'):
            # Run as shell command
            os.system(line[1:])
        else:
            # Try eval first
            try:
                code = compile_with_flags(line, 'eval')
                result = eval(code, self.get_globals(), self.get_locals())

                locals = self.get_locals()
                locals['_'] = locals['_%i' % self.current_statement_index] = result

                if result is not None:
                    out_tokens = self.get_output_prompt_tokens(cli)

                    try:
                        result_str = '%r\n' % (result, )
                    except UnicodeDecodeError:
                        # In Python 2: `__repr__` should return a bytestring,
                        # so to put it in a unicode context could raise an
                        # exception that the 'ascii' codec can't decode certain
                        # characters. Decode as utf-8 in that case.
                        result_str = '%s\n' % repr(result).decode('utf-8')

                    # Align every line to the first one.
                    line_sep = '\n' + ' ' * token_list_width(out_tokens)
                    result_str = line_sep.join(result_str.splitlines()) + '\n'

                    # Write output tokens.
                    out_tokens.extend(_lex_python_result(result_str))
                    cli.print_tokens(out_tokens)
            # If not a valid `eval` expression, run using `exec` instead.
            except SyntaxError:
                code = compile_with_flags(line, 'exec')
                six.exec_(code, self.get_globals(), self.get_locals())

            output.flush()

    @classmethod
    def _handle_exception(cls, cli, e):
        output = cli.output

        # Instead of just calling ``traceback.format_exc``, we take the
        # traceback and skip the bottom calls of this framework.
        t, v, tb = sys.exc_info()
        tblist = traceback.extract_tb(tb)

        for line_nr, tb_tuple in enumerate(tblist):
            if tb_tuple[0] == '<stdin>':
                tblist = tblist[line_nr:]
                break

        l = traceback.format_list(tblist)
        if l:
            l.insert(0, "Traceback (most recent call last):\n")
        l.extend(traceback.format_exception_only(t, v))

        # For Python2: `format_list` and `format_exception_only` return
        # non-unicode strings. Ensure that everything is unicode.
        if six.PY2:
            l = [i.decode('utf-8') if isinstance(i, six.binary_type) else i for i in l]

        tb = ''.join(l)

        # Format exception and write to output.
        # (We use the default style. Most other styles result
        # in unreadable colors for the traceback.)
        tokens = _lex_python_traceback(tb)
        cli.print_tokens(tokens, style=style_from_pygments(DefaultStyle))

        output.write('%s\n' % e)
        output.flush()

    @classmethod
    def _handle_keyboard_interrupt(cls, cli, e):
        output = cli.output

        output.write('\rKeyboardInterrupt\n\n')
        output.flush()


def _lex_python_traceback(tb):
    " Return token list for traceback string. "
    lexer = PythonTracebackLexer()
    return lexer.get_tokens(tb)


def _lex_python_result(tb):
    " Return token list for Python string. "
    lexer = PythonLexer()
    return lexer.get_tokens(tb)


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
          vi_mode=False, history_filename=None, title=None,
          startup_paths=None, patch_stdout=False, return_asyncio_coroutine=False):
    """
    Call this to embed  Python shell at the current point in your program.
    It's similar to `IPython.embed` and `bpython.embed`. ::

        from prompt_toolkit.contrib.repl import embed
        embed(globals(), locals())

    :param vi_mode: Boolean. Use Vi instead of Emacs key bindings.
    :param configure: Callable that will be called with the `PythonRepl` as a first
                      argument, to trigger configuration.
    :param title: Title to be displayed in the terminal titlebar. (None or string.)
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
                      startup_paths=startup_paths)

    if title:
        repl.terminal_title = title

    if configure:
        configure(repl)

    cli = PythonCommandLineInterface(python_input=repl, eventloop=eventloop)

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

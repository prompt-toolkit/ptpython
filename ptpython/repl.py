"""
Utility for creating a Python repl.

::

    from ptpython.repl import embed
    embed(globals(), locals(), vi_mode=False)

"""
from __future__ import unicode_literals

from pygments.lexers import PythonTracebackLexer, PythonLexer
from pygments.token import Token

from prompt_toolkit.document import Document
from prompt_toolkit.eventloop.defaults import use_asyncio_event_loop
from prompt_toolkit.formatted_text import merge_formatted_text, FormattedText
from prompt_toolkit.formatted_text.utils import fragment_list_width
from prompt_toolkit.utils import DummyContext
from prompt_toolkit.shortcuts import set_title, clear_title
from prompt_toolkit.shortcuts import print_formatted_text
from prompt_toolkit.formatted_text import PygmentsTokens

from .python_input import PythonInput
from .eventloop import inputhook

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
        super(PythonRepl, self).__init__(*a, **kw)
        self._load_start_paths()

    def _load_start_paths(self):
        " Start the Read-Eval-Print Loop. "
        if self._startup_paths:
            for path in self._startup_paths:
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        code = compile(f.read(), path, 'exec')
                        six.exec_(code, self.get_globals(), self.get_locals())
                else:
                    output = self.app.output
                    output.write('WARNING | File not found: {}\n\n'.format(path))

    def run(self):
        if self.terminal_title:
            set_title(self.terminal_title)

        while True:
            # Run the UI.
            try:
                text = self.app.run(inputhook=inputhook)
            except EOFError:
                return
            except KeyboardInterrupt:
                # Abort - try again.
                self.default_buffer.document = Document()
            else:
                self._process_text(text)

        if self.terminal_title:
            clear_title()

    def _process_text(self, text):
        line = self.default_buffer.text

        if line and not line.isspace():
            try:
                # Eval and print.
                self._execute(line)
            except KeyboardInterrupt as e:  # KeyboardInterrupt doesn't inherit from Exception.
                self._handle_keyboard_interrupt(e)
            except Exception as e:
                self._handle_exception(e)

            if self.insert_blank_line_after_output:
                self.app.output.write('\n')

            self.current_statement_index += 1
            self.signatures = []

    def _execute(self, line):
        """
        Evaluate the line and print the result.
        """
        output = self.app.output

        # WORKAROUND: Due to a bug in Jedi, the current directory is removed
        # from sys.path. See: https://github.com/davidhalter/jedi/issues/1148
        if '' not in sys.path:
            sys.path.insert(0, '')

        def compile_with_flags(code, mode):
            " Compile code with the right compiler flags. "
            return compile(code, '<stdin>', mode,
                           flags=self.get_compiler_flags(),
                           dont_inherit=True)

        if line.lstrip().startswith('\x1a'):
            # When the input starts with Ctrl-Z, quit the REPL.
            self.app.exit()

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
                    out_prompt = self.get_output_prompt()

                    try:
                        result_str = '%r\n' % (result, )
                    except UnicodeDecodeError:
                        # In Python 2: `__repr__` should return a bytestring,
                        # so to put it in a unicode context could raise an
                        # exception that the 'ascii' codec can't decode certain
                        # characters. Decode as utf-8 in that case.
                        result_str = '%s\n' % repr(result).decode('utf-8')

                    # Align every line to the first one.
                    line_sep = '\n' + ' ' * fragment_list_width(out_prompt)
                    result_str = line_sep.join(result_str.splitlines()) + '\n'

                    # Write output tokens.
                    if self.enable_syntax_highlighting:
                        formatted_output = merge_formatted_text([
                            out_prompt,
                            PygmentsTokens(list(_lex_python_result(result_str))),
                        ])
                    else:
                        formatted_output = FormattedText(
                                out_prompt + [('', result_str)])

                    print_formatted_text(
                        formatted_output, style=self._current_style,
                        style_transformation=self.style_transformation,
                        include_default_pygments_style=False)

            # If not a valid `eval` expression, run using `exec` instead.
            except SyntaxError:
                code = compile_with_flags(line, 'exec')
                six.exec_(code, self.get_globals(), self.get_locals())

            output.flush()

    def _handle_exception(self, e):
        output = self.app.output

        # Instead of just calling ``traceback.format_exc``, we take the
        # traceback and skip the bottom calls of this framework.
        t, v, tb = sys.exc_info()

        # Required for pdb.post_mortem() to work.
        sys.last_type, sys.last_value, sys.last_traceback = t, v, tb

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
        if self.enable_syntax_highlighting:
            tokens = list(_lex_python_traceback(tb))
        else:
            tokens = [(Token, tb)]

        print_formatted_text(
            PygmentsTokens(tokens), style=self._current_style,
            style_transformation=self.style_transformation,
            include_default_pygments_style=False)

        output.write('%s\n' % e)
        output.flush()

    def _handle_keyboard_interrupt(self, e):
        output = self.app.output

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

        with open(config_file, 'rb') as f:
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
        use_asyncio_event_loop()

    # Create REPL.
    repl = PythonRepl(get_globals=get_globals, get_locals=get_locals, vi_mode=vi_mode,
                      history_filename=history_filename, startup_paths=startup_paths)

    if title:
        repl.terminal_title = title

    if configure:
        configure(repl)

    app = repl.app

    # Start repl.
    patch_context = app.patch_stdout_context() if patch_stdout else DummyContext()

    if return_asyncio_coroutine: # XXX
        def coroutine():
            with patch_context:
                for future in app.run_async():
                    yield future
        return coroutine()
    else:
        with patch_context:
            repl.run()

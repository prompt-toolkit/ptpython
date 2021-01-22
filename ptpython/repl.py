"""
Utility for creating a Python repl.

::

    from ptpython.repl import embed
    embed(globals(), locals(), vi_mode=False)

"""
import asyncio
import builtins
import os
import sys
import threading
import traceback
import types
import warnings
from dis import COMPILER_FLAG_NAMES
from enum import Enum
from typing import Any, Callable, ContextManager, Dict, Optional

from prompt_toolkit.formatted_text import (
    HTML,
    AnyFormattedText,
    FormattedText,
    PygmentsTokens,
    StyleAndTextTuples,
    fragment_list_width,
    merge_formatted_text,
    to_formatted_text,
)
from prompt_toolkit.formatted_text.utils import fragment_list_to_text, split_lines
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.patch_stdout import patch_stdout as patch_stdout_context
from prompt_toolkit.shortcuts import (
    PromptSession,
    clear_title,
    print_formatted_text,
    set_title,
)
from prompt_toolkit.styles import BaseStyle
from prompt_toolkit.utils import DummyContext, get_cwidth
from pygments.lexers import PythonLexer, PythonTracebackLexer
from pygments.token import Token

from .python_input import PythonInput

try:
    from ast import PyCF_ALLOW_TOP_LEVEL_AWAIT  # type: ignore
except ImportError:
    PyCF_ALLOW_TOP_LEVEL_AWAIT = 0

__all__ = ["PythonRepl", "enable_deprecation_warnings", "run_config", "embed"]


def _get_coroutine_flag() -> Optional[int]:
    for k, v in COMPILER_FLAG_NAMES.items():
        if v == "COROUTINE":
            return k

    # Flag not found.
    return None


COROUTINE_FLAG: Optional[int] = _get_coroutine_flag()


def _has_coroutine_flag(code: types.CodeType) -> bool:
    if COROUTINE_FLAG is None:
        # Not supported on this Python version.
        return False

    return bool(code.co_flags & COROUTINE_FLAG)


class PythonRepl(PythonInput):
    def __init__(self, *a, **kw) -> None:
        self._startup_paths = kw.pop("startup_paths", None)
        super().__init__(*a, **kw)
        self._load_start_paths()

    def _load_start_paths(self) -> None:
        " Start the Read-Eval-Print Loop. "
        if self._startup_paths:
            for path in self._startup_paths:
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        code = compile(f.read(), path, "exec")
                        exec(code, self.get_globals(), self.get_locals())
                else:
                    output = self.app.output
                    output.write("WARNING | File not found: {}\n\n".format(path))

    def run(self) -> None:
        """
        Run the REPL loop.
        """
        if self.terminal_title:
            set_title(self.terminal_title)

        self._add_to_namespace()

        try:
            while True:
                # Read.
                try:
                    text = self.read()
                except EOFError:
                    return

                # Eval.
                try:
                    result = self.eval(text)
                except KeyboardInterrupt as e:  # KeyboardInterrupt doesn't inherit from Exception.
                    self._handle_keyboard_interrupt(e)
                except SystemExit:
                    return
                except BaseException as e:
                    self._handle_exception(e)
                else:
                    # Print.
                    if result is not None:
                        self.show_result(result)

                    # Loop.
                    self.current_statement_index += 1
                    self.signatures = []

        finally:
            if self.terminal_title:
                clear_title()
            self._remove_from_namespace()

    async def run_async(self) -> None:
        """
        Run the REPL loop, but run the blocking parts in an executor, so that
        we don't block the event loop. Both the input and output (which can
        display a pager) will run in a separate thread with their own event
        loop, this way ptpython's own event loop won't interfere with the
        asyncio event loop from where this is called.

        The "eval" however happens in the current thread, which is important.
        (Both for control-C to work, as well as for the code to see the right
        thread in which it was embedded).
        """
        loop = asyncio.get_event_loop()

        if self.terminal_title:
            set_title(self.terminal_title)

        self._add_to_namespace()

        try:
            while True:
                # Read.
                try:
                    text = await loop.run_in_executor(None, self.read)
                except EOFError:
                    return

                # Eval.
                try:
                    result = await self.eval_async(text)
                except KeyboardInterrupt as e:  # KeyboardInterrupt doesn't inherit from Exception.
                    self._handle_keyboard_interrupt(e)
                except SystemExit:
                    return
                except BaseException as e:
                    self._handle_exception(e)
                else:
                    # Print.
                    if result is not None:
                        await loop.run_in_executor(
                            None, lambda: self.show_result(result)
                        )

                    # Loop.
                    self.current_statement_index += 1
                    self.signatures = []
        finally:
            if self.terminal_title:
                clear_title()
            self._remove_from_namespace()

    def eval(self, line: str) -> object:
        """
        Evaluate the line and print the result.
        """
        # WORKAROUND: Due to a bug in Jedi, the current directory is removed
        # from sys.path. See: https://github.com/davidhalter/jedi/issues/1148
        if "" not in sys.path:
            sys.path.insert(0, "")

        if line.lstrip().startswith("!"):
            # Run as shell command
            os.system(line[1:])
        else:
            # Try eval first
            try:
                code = self._compile_with_flags(line, "eval")
            except SyntaxError:
                # If not a valid `eval` expression, run using `exec` instead.
                code = self._compile_with_flags(line, "exec")
                exec(code, self.get_globals(), self.get_locals())
            else:
                # No syntax errors for eval. Do eval.
                result = eval(code, self.get_globals(), self.get_locals())

                if _has_coroutine_flag(code):
                    result = asyncio.get_event_loop().run_until_complete(result)

                self._store_eval_result(result)
                return result

        return None

    async def eval_async(self, line: str) -> object:
        """
        Evaluate the line and print the result.
        """
        # WORKAROUND: Due to a bug in Jedi, the current directory is removed
        # from sys.path. See: https://github.com/davidhalter/jedi/issues/1148
        if "" not in sys.path:
            sys.path.insert(0, "")

        if line.lstrip().startswith("!"):
            # Run as shell command
            os.system(line[1:])
        else:
            # Try eval first
            try:
                code = self._compile_with_flags(line, "eval")
            except SyntaxError:
                # If not a valid `eval` expression, run using `exec` instead.
                code = self._compile_with_flags(line, "exec")
                exec(code, self.get_globals(), self.get_locals())
            else:
                # No syntax errors for eval. Do eval.
                result = eval(code, self.get_globals(), self.get_locals())

                if _has_coroutine_flag(code):
                    result = await result

                self._store_eval_result(result)
                return result

        return None

    def _store_eval_result(self, result: object) -> None:
        locals: Dict[str, Any] = self.get_locals()
        locals["_"] = locals["_%i" % self.current_statement_index] = result

    def get_compiler_flags(self) -> int:
        return super().get_compiler_flags() | PyCF_ALLOW_TOP_LEVEL_AWAIT

    def _compile_with_flags(self, code: str, mode: str):
        " Compile code with the right compiler flags. "
        return compile(
            code,
            "<stdin>",
            mode,
            flags=self.get_compiler_flags(),
            dont_inherit=True,
        )

    def show_result(self, result: object) -> None:
        """
        Show __repr__ for an `eval` result.
        """
        out_prompt = to_formatted_text(self.get_output_prompt())

        # If the repr is valid Python code, use the Pygments lexer.
        result_repr = repr(result)
        try:
            compile(result_repr, "", "eval")
        except SyntaxError:
            formatted_result_repr = to_formatted_text(result_repr)
        else:
            # Syntactically correct. Format with black and syntax highlight.
            if self.enable_output_formatting:
                # Inline import. Slightly speed up start-up time if black is
                # not used.
                import black

                result_repr = black.format_str(
                    result_repr,
                    mode=black.FileMode(line_length=self.app.output.get_size().columns),
                )

            formatted_result_repr = to_formatted_text(
                PygmentsTokens(list(_lex_python_result(result_repr)))
            )

        # If __pt_repr__ is present, take this. This can return prompt_toolkit
        # formatted text.
        try:
            if hasattr(result, "__pt_repr__"):
                formatted_result_repr = to_formatted_text(
                    getattr(result, "__pt_repr__")()
                )
                if isinstance(formatted_result_repr, list):
                    formatted_result_repr = FormattedText(formatted_result_repr)
        except:
            # For bad code, `__getattr__` can raise something that's not an
            # `AttributeError`. This happens already when calling `hasattr()`.
            pass

        # Align every line to the prompt.
        line_sep = "\n" + " " * fragment_list_width(out_prompt)
        indented_repr: StyleAndTextTuples = []

        lines = list(split_lines(formatted_result_repr))

        for i, fragment in enumerate(lines):
            indented_repr.extend(fragment)

            # Add indentation separator between lines, not after the last line.
            if i != len(lines) - 1:
                indented_repr.append(("", line_sep))

        # Write output tokens.
        if self.enable_syntax_highlighting:
            formatted_output = merge_formatted_text([out_prompt, indented_repr])
        else:
            formatted_output = FormattedText(
                out_prompt + [("", fragment_list_to_text(formatted_result_repr))]
            )

        if self.enable_pager:
            self.print_paginated_formatted_text(to_formatted_text(formatted_output))
        else:
            self.print_formatted_text(to_formatted_text(formatted_output))

        self.app.output.flush()

        if self.insert_blank_line_after_output:
            self.app.output.write("\n")

    def print_formatted_text(self, formatted_text: StyleAndTextTuples) -> None:
        print_formatted_text(
            FormattedText(formatted_text),
            style=self._current_style,
            style_transformation=self.style_transformation,
            include_default_pygments_style=False,
            output=self.app.output,
        )

    def print_paginated_formatted_text(
        self, formatted_text: StyleAndTextTuples
    ) -> None:
        """
        Print formatted text, using --MORE-- style pagination.
        (Avoid filling up the terminal's scrollback buffer.)
        """
        pager_prompt = self.create_pager_prompt()
        size = self.app.output.get_size()

        abort = False

        # Max number of lines allowed in the buffer before painting.
        max_rows = size.rows - 1

        # Page buffer.
        rows_in_buffer = 0
        columns_in_buffer = 0
        page: StyleAndTextTuples = []

        def flush_page() -> None:
            nonlocal page, columns_in_buffer, rows_in_buffer
            self.print_formatted_text(page)
            page = []
            columns_in_buffer = 0
            rows_in_buffer = 0

        def show_pager() -> None:
            nonlocal abort, max_rows

            # Run pager prompt in another thread.
            # Same as for the input. This prevents issues with nested event
            # loops.
            pager_result = None

            def in_thread() -> None:
                nonlocal pager_result
                pager_result = pager_prompt.prompt()

            th = threading.Thread(target=in_thread)
            th.start()
            th.join()

            if pager_result == PagerResult.ABORT:
                print("...")
                abort = True

            elif pager_result == PagerResult.NEXT_LINE:
                max_rows = 1

            elif pager_result == PagerResult.NEXT_PAGE:
                max_rows = size.rows - 1

        # Loop over lines. Show --MORE-- prompt when page is filled.
        for line in split_lines(formatted_text):
            for style, text, *_ in line:
                for c in text:
                    width = get_cwidth(c)

                    # (Soft) wrap line if it doesn't fit.
                    if columns_in_buffer + width > size.columns:
                        # Show pager first if we get too many lines after
                        # wrapping.
                        if rows_in_buffer + 1 >= max_rows:
                            flush_page()
                            show_pager()
                            if abort:
                                return

                        rows_in_buffer += 1
                        columns_in_buffer = 0

                    columns_in_buffer += width
                    page.append((style, c))

            if rows_in_buffer + 1 >= max_rows:
                flush_page()
                show_pager()
                if abort:
                    return
            else:
                page.append(("", "\n"))
                rows_in_buffer += 1
                columns_in_buffer = 0

        flush_page()

    def create_pager_prompt(self) -> PromptSession["PagerResult"]:
        """
        Create pager --MORE-- prompt.
        """
        return create_pager_prompt(self._current_style, self.title)

    def _handle_exception(self, e: BaseException) -> None:
        output = self.app.output

        # Instead of just calling ``traceback.format_exc``, we take the
        # traceback and skip the bottom calls of this framework.
        t, v, tb = sys.exc_info()

        # Required for pdb.post_mortem() to work.
        sys.last_type, sys.last_value, sys.last_traceback = t, v, tb

        tblist = list(traceback.extract_tb(tb))

        for line_nr, tb_tuple in enumerate(tblist):
            if tb_tuple[0] == "<stdin>":
                tblist = tblist[line_nr:]
                break

        l = traceback.format_list(tblist)
        if l:
            l.insert(0, "Traceback (most recent call last):\n")
        l.extend(traceback.format_exception_only(t, v))

        tb_str = "".join(l)

        # Format exception and write to output.
        # (We use the default style. Most other styles result
        # in unreadable colors for the traceback.)
        if self.enable_syntax_highlighting:
            tokens = list(_lex_python_traceback(tb_str))
        else:
            tokens = [(Token, tb_str)]

        print_formatted_text(
            PygmentsTokens(tokens),
            style=self._current_style,
            style_transformation=self.style_transformation,
            include_default_pygments_style=False,
            output=output,
        )

        output.write("%s\n" % e)
        output.flush()

    def _handle_keyboard_interrupt(self, e: KeyboardInterrupt) -> None:
        output = self.app.output

        output.write("\rKeyboardInterrupt\n\n")
        output.flush()

    def _add_to_namespace(self) -> None:
        """
        Add ptpython built-ins to global namespace.
        """
        globals = self.get_globals()

        # Add a 'get_ptpython', similar to 'get_ipython'
        def get_ptpython() -> PythonInput:
            return self

        globals["get_ptpython"] = get_ptpython

    def _remove_from_namespace(self) -> None:
        """
        Remove added symbols from the globals.
        """
        globals = self.get_globals()
        del globals["get_ptpython"]


def _lex_python_traceback(tb):
    " Return token list for traceback string. "
    lexer = PythonTracebackLexer()
    return lexer.get_tokens(tb)


def _lex_python_result(tb):
    " Return token list for Python string. "
    lexer = PythonLexer()
    # Use `get_tokens_unprocessed`, so that we get exactly the same string,
    # without line endings appended. `print_formatted_text` already appends a
    # line ending, and otherwise we'll have two line endings.
    tokens = lexer.get_tokens_unprocessed(tb)
    return [(tokentype, value) for index, tokentype, value in tokens]


def enable_deprecation_warnings() -> None:
    """
    Show deprecation warnings, when they are triggered directly by actions in
    the REPL. This is recommended to call, before calling `embed`.

    e.g. This will show an error message when the user imports the 'sha'
         library on Python 2.7.
    """
    warnings.filterwarnings("default", category=DeprecationWarning, module="__main__")


def run_config(repl: PythonInput, config_file: str = "~/.ptpython/config.py") -> None:
    """
    Execute REPL config file.

    :param repl: `PythonInput` instance.
    :param config_file: Path of the configuration file.
    """
    # Expand tildes.
    config_file = os.path.expanduser(config_file)

    def enter_to_continue() -> None:
        input("\nPress ENTER to continue...")

    # Check whether this file exists.
    if not os.path.exists(config_file):
        print("Impossible to read %r" % config_file)
        enter_to_continue()
        return

    # Run the config file in an empty namespace.
    try:
        namespace: Dict[str, Any] = {}

        with open(config_file, "rb") as f:
            code = compile(f.read(), config_file, "exec")
            exec(code, namespace, namespace)

        # Now we should have a 'configure' method in this namespace. We call this
        # method with the repl as an argument.
        if "configure" in namespace:
            namespace["configure"](repl)

    except Exception:
        traceback.print_exc()
        enter_to_continue()


def embed(
    globals=None,
    locals=None,
    configure: Optional[Callable[[PythonRepl], None]] = None,
    vi_mode: bool = False,
    history_filename: Optional[str] = None,
    title: Optional[str] = None,
    startup_paths=None,
    patch_stdout: bool = False,
    return_asyncio_coroutine: bool = False,
) -> None:
    """
    Call this to embed  Python shell at the current point in your program.
    It's similar to `IPython.embed` and `bpython.embed`. ::

        from prompt_toolkit.contrib.repl import embed
        embed(globals(), locals())

    :param vi_mode: Boolean. Use Vi instead of Emacs key bindings.
    :param configure: Callable that will be called with the `PythonRepl` as a first
                      argument, to trigger configuration.
    :param title: Title to be displayed in the terminal titlebar. (None or string.)
    :param patch_stdout:  When true, patch `sys.stdout` so that background
        threads that are printing will print nicely above the prompt.
    """
    # Default globals/locals
    if globals is None:
        globals = {
            "__name__": "__main__",
            "__package__": None,
            "__doc__": None,
            "__builtins__": builtins,
        }

    locals = locals or globals

    def get_globals():
        return globals

    def get_locals():
        return locals

    # Create REPL.
    repl = PythonRepl(
        get_globals=get_globals,
        get_locals=get_locals,
        vi_mode=vi_mode,
        history_filename=history_filename,
        startup_paths=startup_paths,
    )

    if title:
        repl.terminal_title = title

    if configure:
        configure(repl)

    # Start repl.
    patch_context: ContextManager = (
        patch_stdout_context() if patch_stdout else DummyContext()
    )

    if return_asyncio_coroutine:

        async def coroutine():
            with patch_context:
                await repl.run_async()

        return coroutine()
    else:
        with patch_context:
            repl.run()


class PagerResult(Enum):
    ABORT = "ABORT"
    NEXT_LINE = "NEXT_LINE"
    NEXT_PAGE = "NEXT_PAGE"


def create_pager_prompt(
    style: BaseStyle, title: AnyFormattedText = ""
) -> PromptSession[PagerResult]:
    """
    Create a "continue" prompt for paginated output.
    """
    bindings = KeyBindings()

    @bindings.add("enter")
    @bindings.add("down")
    def next_line(event: KeyPressEvent) -> None:
        event.app.exit(result=PagerResult.NEXT_LINE)

    @bindings.add("space")
    def next_page(event: KeyPressEvent) -> None:
        event.app.exit(result=PagerResult.NEXT_PAGE)

    @bindings.add("q")
    @bindings.add("c-c")
    @bindings.add("c-d")
    @bindings.add("escape", eager=True)
    def no(event: KeyPressEvent) -> None:
        event.app.exit(result=PagerResult.ABORT)

    @bindings.add("<any>")
    def _(event: KeyPressEvent) -> None:
        " Disallow inserting other text. "
        pass

    style

    session: PromptSession[PagerResult] = PromptSession(
        merge_formatted_text(
            [
                title,
                HTML(
                    "<status-toolbar>"
                    "<more> -- MORE -- </more> "
                    "<key>[Enter]</key> Scroll "
                    "<key>[Space]</key> Next page "
                    "<key>[q]</key> Quit "
                    "</status-toolbar>: "
                ),
            ]
        ),
        key_bindings=bindings,
        erase_when_done=True,
        style=style,
    )
    return session

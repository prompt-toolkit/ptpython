"""
Utility for creating a Python async repl based on PythonRepl.

::

    import asyncio
    from ptpython.arepl import embed
    asyncio.run(embed(globals(), locals(), vi_mode=False))
"""

import asyncio
import builtins
import sys
import os
from ast import PyCF_ALLOW_TOP_LEVEL_AWAIT
from dis import COMPILER_FLAG_NAMES
import types
import signal
import contextlib
from typing import Any, Callable, ContextManager, Dict, Optional

from prompt_toolkit.document import Document
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.patch_stdout import patch_stdout as patch_stdout_context
from prompt_toolkit.shortcuts import clear_title, set_title
from prompt_toolkit.utils import DummyContext
from .repl import PythonRepl

__all__ = ["PythonARepl", "embed"]


for k, v in COMPILER_FLAG_NAMES.items():
    if v == "COROUTINE":
        COROUTINE_FLAG = k
        break
else:
    raise RuntimeError("compiler flag COROUTINE value not found")

def has_coroutine_flag(code: types.CodeType) -> bool:
    return bool(code.co_flags & COROUTINE_FLAG)


class PythonARepl(PythonRepl):
    def get_compiler_flags(self) -> int:
        return super().get_compiler_flags() | PyCF_ALLOW_TOP_LEVEL_AWAIT

    async def run_async(self) -> None:
        if self.terminal_title:
            set_title(self.terminal_title)

        while True:
            # Capture the current input_mode in order to restore it after reset,
            # for ViState.reset() sets it to InputMode.INSERT unconditionally and
            # doesn't accept any arguments.
            def pre_run(
                last_input_mode: InputMode = self.app.vi_state.input_mode,
            ) -> None:
                if self.vi_keep_last_used_mode:
                    self.app.vi_state.input_mode = last_input_mode

                if not self.vi_keep_last_used_mode and self.vi_start_in_navigation_mode:
                    self.app.vi_state.input_mode = InputMode.NAVIGATION

            # Run the UI.
            try:
                text = await self.app.run_async(pre_run=pre_run)
            except EOFError:
                return
            except KeyboardInterrupt:
                # Abort - try again.
                self.default_buffer.document = Document()
            else:
                await self._process_text_async(text)

        if self.terminal_title:
            clear_title()

    async def _process_text_async(self, line: str) -> None:
        if line and not line.isspace():
            if self.insert_blank_line_after_input:
                self.app.output.write("\n")

            try:
                # Eval and print.
                await self._execute_async(line)
            except KeyboardInterrupt as e:  # KeyboardInterrupt doesn't inherit from Exception.
                self._handle_keyboard_interrupt(e)
            except asyncio.CancelledError as e: # CancelledError doesn't inherit from Exception.
                self._handle_cancelled(e)
            except Exception as e:
                self._handle_exception(e)

            if self.insert_blank_line_after_output:
                self.app.output.write("\n")

            self.current_statement_index += 1
            self.signatures = []

    async def _execute_async(self, line: str) -> None:
        """
        Evaluate the line and print the result.
        """
        # WORKAROUND: Due to a bug in Jedi, the current directory is removed
        # from sys.path. See: https://github.com/davidhalter/jedi/issues/1148
        if "" not in sys.path:
            sys.path.insert(0, "")

        def compile_with_flags(code: str, mode: str, flags: int = 0):
            " Compile code with the right compiler flags. "
            return compile(
                code,
                "<stdin>",
                mode,
                flags=flags|self.get_compiler_flags(),
                dont_inherit=True,
            )

        # If the input is single line, remove leading whitespace.
        # (This doesn't have to be a syntax error.)
        if len(line.splitlines()) == 1:
            line = line.strip()

        if line.lstrip().startswith("\x1a"):
            # When the input starts with Ctrl-Z, quit the REPL.
            self.app.exit()

        elif line.lstrip().startswith("!"):
            # Run as shell command
            os.system(line[1:])
        else:
            # Try eval first
            try:
                code = compile_with_flags(line, "eval")
                if has_coroutine_flag(code):
                    result = await self._execute_task(code)
                else:
                    result = eval(code, self.get_globals(), self.get_locals())
                self._handle_result(result)

            # If not a valid `eval` expression, run using `exec` instead.
            except SyntaxError:
                code = compile_with_flags(line, "exec")
                if has_coroutine_flag(code):
                    await self._execute_task(code)
                else:
                    exec(code, self.get_globals(), self.get_locals())

    async def _execute_task(self, code: types.CodeType):
        loop = asyncio.get_running_loop()
        coro = eval(code, self.get_globals(), self.get_locals())
        task = loop.create_task(coro)
        interrupt = loop.create_future()
        try:
            loop.add_signal_handler(signal.SIGINT, interrupt.set_result, None)
            done, pending = await asyncio.wait(
                {task, interrupt}, return_when=asyncio.FIRST_COMPLETED)
            if task in done:
                return task.result()
            else:
                self.app.output.write("detached, return task object\n")
                self._handle_result(task)
                raise KeyboardInterrupt
        finally:
            loop.remove_signal_handler(signal.SIGINT)

    def _handle_result(self, result: Any) -> None:
        locals: Dict[str, Any] = self.get_locals()
        locals["_"] = locals["_%i" % self.current_statement_index] = result

        if result is not None:
            self.show_result(result)

    def _handle_cancelled(self, e: asyncio.CancelledError) -> None:
        output = self.app.output

        output.write("\rCancelledError\n\n")
        output.flush()


async def embed(
    globals=None,
    locals=None,
    configure: Optional[Callable[[PythonRepl], None]] = None,
    vi_mode: bool = False,
    history_filename: Optional[str] = None,
    title: Optional[str] = None,
    startup_paths=None,
    patch_stdout: bool = True,
) -> None:
    """
    Await this to embed Python shell in your program.
    It's similar to `ptpython.repl.embed`. ::
        from ptpython.arepl import embed
        await embed(globals(), locals())
    :param vi_mode: Boolean. Use Vi instead of Emacs key bindings.
    :param configure: Callable that will be called with the `PythonRepl` as a first
                      argument, to trigger configuration.
    :param title: Title to be displayed in the terminal titlebar. (None or string.)
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
    repl = PythonARepl(
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

    with patch_context:
        await repl.run_async()


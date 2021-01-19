
Concurrency-related challenges regarding embedding of ptpython in asyncio code
==============================================================================

Things we want to be possible
-----------------------------

- embed blocking ptpython in non-asyncio code.
- embed blocking ptpython in asyncio code (the event loop will block).
- embed awaitable ptpython in asyncio code (the loop will continue).
- react to resize events (SIGWINCH).
- support top-level await.
- Be able to patch_stdout, so that logging messages from another thread will be
  printed above the prompt.
- It should be possible to handle `KeyboardInterrupt` during evaluation of an
  expression. (This only works if the "eval" happens in the main thread.)
- The "eval" should happen in the same thread in which embed() was used.

- create asyncio background tasks and have them run in the ptpython event loop.
- create asyncio background tasks and have ptpython run in a separate, isolated loop.

Limitations of asyncio/python
-----------------------------

- Spawning a new event loop in an existing event loop (from in a coroutine) is
  not allowed. We can however spawn the event loop in a separate thread, and
  wait for that thread to finish.

- We can't listen to SIGWINCH signals, but prompt_toolkit's terminal size
  polling solves that.

- For patch_stdout to work correctly, we have to know what prompt_toolkit
  application is running on the terminal, and tell that application to print
  the output and redraw itself.

- Handling of `KeyboardInterrupt`.

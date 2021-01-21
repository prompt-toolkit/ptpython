
Concurrency-related challenges regarding embedding of ptpython in asyncio code
==============================================================================

Things we want to be possible
-----------------------------

- Embed blocking ptpython in non-asyncio code (the normal use case).
- Embed blocking ptpython in asyncio code (the event loop will block).
- Embed awaitable ptpython in asyncio code (the loop will continue).
- React to resize events (SIGWINCH).
- Support top-level await.
- Be able to patch_stdout, so that logging messages from another thread will be
  printed above the prompt.
- It should be possible to handle `KeyboardInterrupt` during evaluation of an
  expression.
- The "eval" should happen in the same thread from where embed() was called.


Limitations of asyncio/python
-----------------------------

- We can only listen to SIGWINCH signal (resize) events in the main thread.

- Usage of Control-C for triggering a `KeyboardInterrupt` only works for code
  running in the main thread. (And only if the terminal was not set in raw
  input mode).

- Spawning a new event loop from within a coroutine, that's being executed in
  an existing event loop is not allowed in asyncio. We can however spawn any
  event loop in a separate thread, and wait for that thread to finish.

- For patch_stdout to work correctly, we have to know what prompt_toolkit
  application is running on the terminal, then tell that application to print
  the output and redraw itself.


Additional challenges for IPython
---------------------------------

IPython supports integration of 3rd party event loops (for various GUI
toolkits). These event loops are supposed to continue running while we are
prompting for input. In an asyncio environment, it means that there are
situations where we have to juggle three event loops:

- The asyncio loop in which the code was embedded.
- The asyncio loop from the prompt.
- The 3rd party GUI loop. 

Approach taken in ptpython 3.0.11
---------------------------------

For ptpython, the most reliable solution is to to run the prompt_toolkit input
prompt in a separate background thread. This way it can use its own asyncio
event loop without ever having to interfere with whatever runs in the main
thread.

Then, depending on how we embed, we do the following:
When a normal blocking embed is used:
    * We start the UI thread for the input, and do a blocking wait on
      `thread.join()` here.
    * The "eval" happens in the main thread.
    * The "print" happens also in the main thread. Unless a pager is shown,
      which is also a prompt_toolkit application, then the pager itself is runs
      also in another thread, similar to the way we do the input.

When an awaitable embed is used, for embedding in a coroutine, but having the
event loop continue:
    * We run the input method from the blocking embed in an asyncio executor
      and do an `await loop.run_in_excecutor(...)`.
    * The "eval" happens again in the main thread.
    * "print" is also similar, except that the pager code (if used) runs in an
      executor too.

This means that the prompt_toolkit application code will always run in a
different thread. It means it won't be able to respond to SIGWINCH (window
resize events), but prompt_toolkit's 3.0.11 has now terminal size polling which
solves this.

Control-C key presses won't interrupt the main thread while we wait for input,
because the prompt_toolkit application turns the terminal in raw mode, while
it's reading, which means that it will receive control-c key presses as raw
data in its own thread.

Top-level await works in most situations as expected.
- If a blocking embed is used. We execute ``loop.run_until_complete(code)``.
  This assumes that the blocking embed is not used in a coroutine of a running
  event loop, otherwise, this will attempt to start a nested event loop, which
  asyncio does not support. In that case we will get an exception.
- If an awaitable embed is used. We literally execute ``await code``. This will
  integrate nicely in the current event loop.

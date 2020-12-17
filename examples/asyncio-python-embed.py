#!/usr/bin/env python
"""
(Python >3.3)

This is an example of how we can embed a Python REPL into an asyncio
application. In this example, we have one coroutine that runs in the
background, prints some output and alters a global state. The REPL, which runs
inside another coroutine can access and change this global state, interacting
with the running asyncio application.
The ``patch_stdout`` option makes sure that when another coroutine is writing
to stdout, it won't break the input line, but instead writes nicely above the
prompt.
"""
import asyncio

from ptpython.repl import embed

loop = asyncio.get_event_loop()
counter = [0]


async def print_counter():
    """
    Coroutine that prints counters and saves it in a global variable.
    """
    while True:
        print("Counter: %i" % counter[0])
        counter[0] += 1
        await asyncio.sleep(3)


async def interactive_shell():
    """
    Coroutine that starts a Python REPL from which we can access the global
    counter variable.
    """
    print(
        'You should be able to read and update the "counter[0]" variable from this shell.'
    )
    try:
        await embed(globals=globals(), return_asyncio_coroutine=True, patch_stdout=True)
    except EOFError:
        # Stop the loop when quitting the repl. (Ctrl-D press.)
        loop.stop()


def main():
    asyncio.ensure_future(print_counter())
    asyncio.ensure_future(interactive_shell())

    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    main()

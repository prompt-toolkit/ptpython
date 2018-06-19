"""
Tool for embedding a REPL inside a Python 3 asyncio process.
See ./examples/asyncio-ssh-python-embed.py for a demo.

Note that the code in this file is Python 3 only. However, we
should make sure not to use Python 3-only syntax, because this
package should be installable in Python 2 as well!
"""
from __future__ import unicode_literals

import asyncio
import asyncssh

from prompt_toolkit.input import PipeInput
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.layout.screen import Size
from prompt_toolkit.shortcuts import create_asyncio_eventloop
from prompt_toolkit.terminal.vt100_output import Vt100_Output

from ptpython.repl import PythonRepl

__all__ = (
    'ReplSSHServerSession',
)


class ReplSSHServerSession(asyncssh.SSHServerSession):
    """
    SSH server session that runs a Python REPL.

    :param get_globals: callable that returns the current globals.
    :param get_locals: (optional) callable that returns the current locals.
    """
    def __init__(self, get_globals, get_locals=None):
        assert callable(get_globals)
        assert get_locals is None or callable(get_locals)

        self._chan = None

        def _globals():
            data = get_globals()
            data.setdefault('print', self._print)
            return data

        repl = PythonRepl(get_globals=_globals,
                          get_locals=get_locals or _globals)

        # Disable open-in-editor and system prompt. Because it would run and
        # display these commands on the server side, rather than in the SSH
        # client.
        repl.enable_open_in_editor = False
        repl.enable_system_bindings = False

        # PipInput object, for sending input in the CLI.
        # (This is something that we can use in the prompt_toolkit event loop,
        # but still write date in manually.)
        self._input_pipe = PipeInput()

        # Output object. Don't render to the real stdout, but write everything
        # in the SSH channel.
        class Stdout(object):
            def write(s, data):
                if self._chan is not None:
                    self._chan.write(data.replace('\n', '\r\n'))

            def flush(s):
                pass

        # Create command line interface.
        self.cli = CommandLineInterface(
            application=repl.create_application(),
            eventloop=create_asyncio_eventloop(),
            input=self._input_pipe,
            output=Vt100_Output(Stdout(), self._get_size))

        self._callbacks = self.cli.create_eventloop_callbacks()

    def _get_size(self):
        """
        Callable that returns the current `Size`, required by Vt100_Output.
        """
        if self._chan is None:
            return Size(rows=20, columns=79)
        else:
            width, height, pixwidth, pixheight = self._chan.get_terminal_size()
            return Size(rows=height, columns=width)

    def connection_made(self, chan):
        """
        Client connected, run repl in coroutine.
        """
        self._chan = chan

        # Run REPL interface.
        f = asyncio.ensure_future(self.cli.run_async())

        # Close channel when done.
        def done(_):
            chan.close()
            self._chan = None
        f.add_done_callback(done)

    def shell_requested(self):
        return True

    def terminal_size_changed(self, width, height, pixwidth, pixheight):
        """
        When the terminal size changes, report back to CLI.
        """
        self._callbacks.terminal_size_changed()

    def data_received(self, data, datatype):
        """
        When data is received, send to inputstream of the CLI and repaint.
        """
        self._input_pipe.send(data)

    def _print(self, *data, **kw):
        """
        _print(self, *data, sep=' ', end='\n', file=None)

        Alternative 'print' function that prints back into the SSH channel.
        """
        # Pop keyword-only arguments. (We cannot use the syntax from the
        # signature. Otherwise, Python2 will give a syntax error message when
        # installing.)
        sep = kw.pop('sep', ' ')
        end = kw.pop('end', '\n')
        _ = kw.pop('file', None)
        assert not kw, 'Too many keyword-only arguments'

        data = sep.join(map(str, data))
        self._chan.write(data + end)

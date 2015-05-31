#!/usr/bin/env python
"""
Example of running the Python REPL through an SSH connection in an asyncio process.

This requires Python 3.
"""
import asyncio
import asyncssh
import logging

from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.layout.screen import Size
from prompt_toolkit.shortcuts import create_asyncio_eventloop
from prompt_toolkit.terminal.vt100_output import Vt100_Output
from prompt_toolkit.input import PipeInput

from ptpython.repl import PythonRepl

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


class MySSHServerSession(asyncssh.SSHServerSession):
    def __init__(self, get_globals, get_locals):
        self._chan = None

        def _globals():
            data = {'print': self._print}
            data.update(get_globals())
            return data

        repl = PythonRepl(get_globals=_globals, get_locals=get_locals)

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

        def corot():
            # Run REPL interface.
            yield from self.cli.run_async()

            # Close channel when done.
            chan.close()
            self._chan = None
        asyncio.async(corot())

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

    def _print(self, *data, sep=' ', end='\n', file=None):
        """
        Alternative 'print' function that prints back into the SSH channel.
        """
        data = sep.join(map(str, data))
        self._chan.write(data + end)


class MySSHServer(asyncssh.SSHServer):
    def __init__(self, get_globals=None, get_locals=None):
        self.get_globals = get_globals
        self.get_locals = get_locals

    def begin_auth(self, username):
        return False

    def session_requested(self):
        return MySSHServerSession(self.get_globals, self.get_locals)


def main(port=8222):
    """
    Main, example that starts an SSH server.
    """
    loop = asyncio.get_event_loop()

    # Namespace that expose in the REPL.
    environ = {}

    # Start SSH server.
    def create_server():
        return MySSHServer(lambda: environ, lambda: environ)

    print('Listening on :%i' % port)
    print('To connect, do "ssh localhost -p %i"' % port)

    loop.run_until_complete(
        asyncssh.create_server(create_server, '', port,
                               server_host_keys=['/etc/ssh/ssh_host_dsa_key']))

    # Run eventloop.
    loop.run_forever()


if __name__ == '__main__':
    main()

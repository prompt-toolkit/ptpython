#!/usr/bin/env python
"""
Example of running the Python REPL through an SSH connection in an asyncio process.
This requires Python 3, asyncio and asyncssh.

Run this example and then SSH to localhost, port 8222.
"""
import asyncio
import logging

import asyncssh

from ptpython.contrib.asyncssh_repl import ReplSSHServerSession

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


class MySSHServer(asyncssh.SSHServer):
    """
    Server without authentication, running `ReplSSHServerSession`.
    """

    def __init__(self, get_namespace):
        self.get_namespace = get_namespace

    def begin_auth(self, username):
        # No authentication.
        return False

    def session_requested(self):
        return ReplSSHServerSession(self.get_namespace)


async def main(port: int = 8222) -> None:
    """
    Example that starts the REPL through an SSH server.
    """
    # Namespace exposed in the REPL.
    environ = {"hello": "world"}

    # Start SSH server.
    def create_server() -> MySSHServer:
        return MySSHServer(lambda: environ)

    print("Listening on :%i" % port)
    print('To connect, do "ssh localhost -p %i"' % port)

    await asyncssh.create_server(
        create_server, "", port, server_host_keys=["/etc/ssh/ssh_host_dsa_key"]
    )
    await asyncio.Future()  # Wait forever.


if __name__ == "__main__":
    asyncio.run(main())

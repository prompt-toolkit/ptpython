#!/usr/bin/env python
"""
Serve a ptpython console using both telnet and ssh.

Thanks to Vincent Michel for this!
https://gist.github.com/vxgmichel/7685685b3e5ead04ada4a3ba75a48eef
"""

import asyncio
import pathlib

import asyncssh
from prompt_toolkit import print_formatted_text
from prompt_toolkit.contrib.ssh.server import PromptToolkitSSHServer
from prompt_toolkit.contrib.telnet.server import TelnetServer

from ptpython.repl import embed


def ensure_key(filename="ssh_host_key"):
    path = pathlib.Path(filename)
    if not path.exists():
        rsa_key = asyncssh.generate_private_key("ssh-rsa")
        path.write_bytes(rsa_key.export_private_key())
    return str(path)


async def interact(connection=None):
    global_dict = {**globals(), "print": print_formatted_text}
    await embed(return_asyncio_coroutine=True, globals=global_dict)


async def main(ssh_port=8022, telnet_port=8023):
    ssh_server = PromptToolkitSSHServer(interact=interact)
    await asyncssh.create_server(
        lambda: ssh_server, "", ssh_port, server_host_keys=[ensure_key()]
    )
    print(f"Running ssh server on port {ssh_port}...")

    telnet_server = TelnetServer(interact=interact, port=telnet_port)
    telnet_server.start()
    print(f"Running telnet server on port {telnet_port}...")

    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python
"""
ptpython: Interactive Python shell.
Usage:
    ptpython [ --vi ]
             [ --config-dir=<directory> ] [ --interactive=<filename> ]
             [--] [ <arg>... ]
    ptpython -h | --help

Options:
    --vi                         : Use Vi keybindings instead of Emacs bindings.
    --config-dir=<directory>     : Pass config directory. By default '$XDG_CONFIG_HOME/ptpython'.
    -i, --interactive=<filename> : Start interactive shell after executing this file.

Other environment variables:
PYTHONSTARTUP: file executed on interactive startup (no default)
"""
import argparse
import os
import pathlib
import sys
from typing import Tuple

import appdirs
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import print_formatted_text

from ptpython.repl import embed, enable_deprecation_warnings, run_config

__all__ = ["create_parser", "get_config_and_history_file", "run"]


class _Parser(argparse.ArgumentParser):
    def print_help(self):
        super().print_help()
        print("Other environment variables:")
        print("PYTHONSTARTUP: file executed on interactive startup (no default)")


def create_parser() -> _Parser:
    parser = _Parser(description="ptpython: Interactive Python shell.")
    parser.add_argument("--vi", action="store_true", help="Enable Vi key bindings")
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Start interactive shell after executing this file.",
    )
    parser.add_argument(
        "--config-file", type=str, help="Location of configuration file."
    )
    parser.add_argument("--history-file", type=str, help="Location of history file.")
    parser.add_argument(
        "-V", "--version", action="store_true", help="Print version and exit."
    )
    parser.add_argument("args", nargs="*", help="Script and arguments")
    return parser


def get_config_and_history_file(namespace: argparse.Namespace) -> Tuple[str, str]:
    """
    Check which config/history files to use, ensure that the directories for
    these files exist, and return the config and history path.
    """
    config_dir = appdirs.user_config_dir("ptpython", "prompt_toolkit")
    data_dir = appdirs.user_data_dir("ptpython", "prompt_toolkit")

    # Create directories.
    for d in (config_dir, data_dir):
        pathlib.Path(d).mkdir(parents=True, exist_ok=True)

    # Determine config file to be used.
    config_file = os.path.join(config_dir, "config.py")
    legacy_config_file = os.path.join(os.path.expanduser("~/.ptpython"), "config.py")

    warnings = []

    # Config file
    if namespace.config_file:
        # Override config_file.
        config_file = os.path.expanduser(namespace.config_file)

    elif os.path.isfile(legacy_config_file):
        # Warn about the legacy configuration file.
        warnings.append(
            HTML(
                "    <i>~/.ptpython/config.py</i> is deprecated, move your configuration to <i>%s</i>\n"
            )
            % config_file
        )
        config_file = legacy_config_file

    # Determine history file to be used.
    history_file = os.path.join(data_dir, "history")
    legacy_history_file = os.path.join(os.path.expanduser("~/.ptpython"), "history")

    if namespace.history_file:
        # Override history_file.
        history_file = os.path.expanduser(namespace.history_file)

    elif os.path.isfile(legacy_history_file):
        # Warn about the legacy history file.
        warnings.append(
            HTML(
                "    <i>~/.ptpython/history</i> is deprecated, move your history to <i>%s</i>\n"
            )
            % history_file
        )
        history_file = legacy_history_file

    # Print warnings.
    if warnings:
        print_formatted_text(HTML("<u>Warning:</u>"))
        for w in warnings:
            print_formatted_text(w)

    return config_file, history_file


def run() -> None:
    a = create_parser().parse_args()

    config_file, history_file = get_config_and_history_file(a)

    # Startup path
    startup_paths = []
    if "PYTHONSTARTUP" in os.environ:
        startup_paths.append(os.environ["PYTHONSTARTUP"])

    # --interactive
    if a.interactive and a.args:
        startup_paths.append(a.args[0])
        sys.argv = a.args

    # Add the current directory to `sys.path`.
    if sys.path[0] != "":
        sys.path.insert(0, "")

    # When a file has been given, run that, otherwise start the shell.
    if a.args and not a.interactive:
        sys.argv = a.args
        path = a.args[0]
        with open(path, "rb") as f:
            code = compile(f.read(), path, "exec")
            # NOTE: We have to pass an empty dictionary as namespace. Omitting
            #       this argument causes imports to not be found. See issue #326.
            exec(code, {})

    # Run interactive shell.
    else:
        enable_deprecation_warnings()

        # Apply config file
        def configure(repl) -> None:
            if os.path.exists(config_file):
                run_config(repl, config_file)

        import __main__

        embed(
            vi_mode=a.vi,
            history_filename=history_file,
            configure=configure,
            locals=__main__.__dict__,
            globals=__main__.__dict__,
            startup_paths=startup_paths,
            title="Python REPL (ptpython)",
        )


if __name__ == "__main__":
    run()

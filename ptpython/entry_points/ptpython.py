#!/usr/bin/env python
"""
ptpython: Interactive Python shell.
Usage:
    ptpython [ --vi ] [ --history=<filename> ] [ --no-colors ]
             [ --autocompletion=<type> ] [ --always-multiline ]
             [ --interactive=<filename> ] [--] [ <file> <arg>... ]
    ptpython -h | --help

Options:
    --vi                     : Use Vi keybindings instead of Emacs bindings.
    --history=<filename>     : Path to history file.
    --autocompletion=<type>  : Type of autocompletion. This can be 'popup-menu'
                               or 'horizontal-menu'.
    --always-multiline       : Always enable multiline mode.
    --interactive=<filename> : Start interactive shell after executing this file.

Other environment variables:
PYTHONSTARTUP: file executed on interactive startup (no default)
"""
import docopt
import os
import six
import sys

from prompt_toolkit.contrib.repl import embed
from prompt_toolkit.contrib.python_input import AutoCompletionStyle


def run():
    a = docopt.docopt(__doc__)

    vi_mode = bool(a['--vi'])
    no_colors = bool(a['--no-colors'])

    # Create globals/locals dict.
    globals_, locals_ = {}, {}

    # Log history
    if a['--history']:
        history_filename = os.path.expanduser(a['--history'])
    else:
        history_filename = os.path.expanduser('~/.ptpython_history')

    # Autocompletion type
    if a['--autocompletion'] in (
            AutoCompletionStyle.POPUP_MENU,
            AutoCompletionStyle.HORIZONTAL_MENU,
            AutoCompletionStyle.NONE):
        autocompletion_style = a['--autocompletion']
    else:
        autocompletion_style = AutoCompletionStyle.POPUP_MENU

    # Always multiline
    always_multiline = bool(a['--always-multiline'])

    # Startup path
    startup_paths = []
    if 'PYTHONSTARTUP' in os.environ:
        startup_paths.append(os.environ['PYTHONSTARTUP'])

    # --interactive
    if a['--interactive']:
        startup_paths.append(a['--interactive'])

    # Add the current directory to `sys.path`.
    sys.path.append('.')

    # When a file has been given, run that, otherwise start the shell.
    if a['<file>']:
        sys.argv = [a['<file>']] + a['<arg>']
        six.exec_(compile(open(a['<file>'], "rb").read(), a['<file>'], 'exec'))
    else:
        # Run interactive shell.
        embed(globals_, locals_, vi_mode=vi_mode, history_filename=history_filename,
              no_colors=no_colors, autocompletion_style=autocompletion_style,
              startup_paths=startup_paths, always_multiline=always_multiline)

if __name__ == '__main__':
    run()

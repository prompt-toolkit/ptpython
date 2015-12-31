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
    --config-dir=<directory>     : Pass config directory. By default '~/.ptpython/'.
    -i, --interactive=<filename> : Start interactive shell after executing this file.

Other environment variables:
PYTHONSTARTUP: file executed on interactive startup (no default)
"""
from __future__ import absolute_import, unicode_literals

import docopt
import os
import six
import sys

from ptpython.repl import embed, enable_deprecation_warnings, run_config


def run():
    a = docopt.docopt(__doc__)

    vi_mode = bool(a['--vi'])
    config_dir = os.path.expanduser(a['--config-dir'] or '~/.ptpython/')

    # Create config directory.
    if not os.path.isdir(config_dir):
        os.mkdir(config_dir)

    # Startup path
    startup_paths = []
    if 'PYTHONSTARTUP' in os.environ:
        startup_paths.append(os.environ['PYTHONSTARTUP'])

    # --interactive
    if a['--interactive']:
        startup_paths.append(a['--interactive'])
        sys.argv = [a['--interactive']] + a['<arg>']

    # Add the current directory to `sys.path`.
    if sys.path[0] != '':
        sys.path.insert(0, '')

    # When a file has been given, run that, otherwise start the shell.
    if a['<arg>'] and not a['--interactive']:
        sys.argv = a['<arg>']
        six.exec_(compile(open(a['<arg>'][0], "rb").read(), a['<arg>'][0], 'exec'))

    # Run interactive shell.
    else:
        enable_deprecation_warnings()

        # Apply config file
        def configure(repl):
            path = os.path.join(config_dir, 'config.py')
            if os.path.exists(path):
                run_config(repl, path)

        embed(vi_mode=vi_mode,
              history_filename=os.path.join(config_dir, 'history'),
              configure=configure,
              startup_paths=startup_paths,
              title='Python REPL (ptpython)')

if __name__ == '__main__':
    run()

#!/usr/bin/env python
"""
ptipython: IPython interactive shell with the `prompt_toolkit` front-end.
Usage:
    ptpython [ --vi ]
             [ --config-dir=<directory> ]
             [--] [ <file> <arg>... ]
    ptpython -h | --help

Options:
    --vi                     : Use Vi keybindings instead of Emacs bindings.
    --config-dir=<directory> : Pass config directory. By default '~/.ptpython/'.
"""
from __future__ import absolute_import, unicode_literals

import docopt
import os
import six
import sys


def run():
    a = docopt.docopt(__doc__)

    vi_mode = bool(a['--vi'])
    config_dir = os.path.expanduser(a['--config-dir'] or '~/.ptpython/')

    # If IPython is not available, show message and exit here with error status
    # code.
    try:
        import IPython
    except ImportError:
        print('IPython not found. Please install IPython (pip install ipython).')
        sys.exit(1)
    else:
        from ptpython.ipython import embed
        from ptpython.repl import run_config, enable_deprecation_warnings

    # Add the current directory to `sys.path`.
    sys.path.append('.')

    # When a file has been given, run that, otherwise start the shell.
    if a['<file>']:
        sys.argv = [a['<file>']] + a['<arg>']
        six.exec_(compile(open(a['<file>'], "rb").read(), a['<file>'], 'exec'))
    else:
        enable_deprecation_warnings()

        # Create an empty namespace for this interactive shell. (If we don't do
        # that, all the variables from this function will become available in
        # the IPython shell.)
        user_ns = {}

        # Apply config file
        def configure(repl):
            path = os.path.join(config_dir, 'config.py')
            if os.path.exists(path):
                run_config(repl, path)

        # Run interactive shell.
        embed(vi_mode=vi_mode, 
              history_filename=os.path.join(config_dir, 'history'),
              configure=configure,
              user_ns=user_ns)


if __name__ == '__main__':
    run()

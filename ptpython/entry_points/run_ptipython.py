#!/usr/bin/env python
"""
ptipython: IPython interactive shell with the `prompt_toolkit` front-end.
Usage:
    ptpython [ --vi ]
             [ --config-dir=<directory> ] [ --interactive=<filename> ]
             [--] [ <arg>... ]
    ptpython -h | --help

Options:
    --vi                     : Use Vi keybindings instead of Emacs bindings.
    --config-dir=<directory> : Pass config directory. By default '~/.ptpython/'.
    -i, --interactive=<filename> : Start interactive shell after executing this file.
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

    # Create config directory.
    if not os.path.isdir(config_dir):
        os.mkdir(config_dir)

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
    if sys.path[0] != '':
        sys.path.insert(0, '')

    # When a file has been given, run that, otherwise start the shell.
    if a['<arg>'] and not a['--interactive']:
        sys.argv = a['<arg>']
        six.exec_(compile(open(a['<arg>'][0], "rb").read(), a['<arg>'][0], 'exec'))
    else:
        enable_deprecation_warnings()

        # Create an empty namespace for this interactive shell. (If we don't do
        # that, all the variables from this function will become available in
        # the IPython shell.)
        user_ns = {}

        # Startup path
        startup_paths = []
        if 'PYTHONSTARTUP' in os.environ:
            startup_paths.append(os.environ['PYTHONSTARTUP'])

        # --interactive
        if a['--interactive']:
            startup_paths.append(a['--interactive'])
            sys.argv = [a['--interactive']] + a['<arg>']

        # exec scripts from startup paths
        for path in startup_paths:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    code = compile(f.read(), path, 'exec')
                    six.exec_(code, user_ns, user_ns)
            else:
                print('File not found: {}\n\n'.format(path))
                sys.exit(1)

        # Apply config file
        def configure(repl):
            path = os.path.join(config_dir, 'config.py')
            if os.path.exists(path):
                run_config(repl, path)

        # Run interactive shell.
        embed(vi_mode=vi_mode,
              history_filename=os.path.join(config_dir, 'history'),
              configure=configure,
              user_ns=user_ns,
              title='IPython REPL (ptipython)')


if __name__ == '__main__':
    run()

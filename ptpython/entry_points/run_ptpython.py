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
from __future__ import absolute_import, unicode_literals, print_function

import appdirs
import docopt
import os
import six
import sys

from ptpython.repl import embed, enable_deprecation_warnings, run_config


def run():
    a = docopt.docopt(__doc__)

    vi_mode = bool(a['--vi'])

    config_dir = appdirs.user_config_dir('ptpython', 'prompt_toolkit')
    data_dir = appdirs.user_data_dir('ptpython', 'prompt_toolkit')

    if a['--config-dir']:
        # Override config_dir.
        config_dir = os.path.expanduser(a['--config-dir'])
    else:
        # Warn about the legacy directory.
        legacy_dir = os.path.expanduser('~/.ptpython')
        if os.path.isdir(legacy_dir):
            print('{0} is deprecated, migrate your configuration to {1}'.format(legacy_dir, config_dir))

    # Create directories.
    for d in (config_dir, data_dir):
        if not os.path.isdir(d) and not os.path.islink(d):
            os.mkdir(d)

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
        path = a['<arg>'][0]
        with open(path, 'rb') as f:
            code = compile(f.read(), path, 'exec')
            # NOTE: We have to pass an empty dictionary as namespace. Omitting
            #       this argument causes imports to not be found. See issue #326.
            six.exec_(code, {})

    # Run interactive shell.
    else:
        enable_deprecation_warnings()

        # Apply config file
        def configure(repl):
            path = os.path.join(config_dir, 'config.py')
            if os.path.exists(path):
                run_config(repl, path)

        import __main__
        embed(vi_mode=vi_mode,
              history_filename=os.path.join(data_dir, 'history'),
              configure=configure,
              locals=__main__.__dict__,
              globals=__main__.__dict__,
              startup_paths=startup_paths,
              title='Python REPL (ptpython)')

if __name__ == '__main__':
    run()

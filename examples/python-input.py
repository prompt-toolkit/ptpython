#!/usr/bin/env python
"""
"""
from __future__ import unicode_literals

from ptpython.python_input import PythonCommandLineInterface


def main():
    cli = PythonCommandLineInterface()

    code_obj = cli.cli.read_input()
    print('You said: ' + code_obj.text)


if __name__ == '__main__':
    main()

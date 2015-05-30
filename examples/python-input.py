#!/usr/bin/env python
"""
"""
from __future__ import unicode_literals

from prompt_toolkit.shortcuts import create_eventloop
from ptpython.python_input import PythonCommandLineInterface


def main():
    eventloop = create_eventloop()
    try:
        cli = PythonCommandLineInterface(eventloop)

        code_obj = cli.run()
        print('You said: ' + code_obj.text)
    finally:
        eventloop.close()


if __name__ == '__main__':
    main()

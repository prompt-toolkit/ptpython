#!/usr/bin/env python
"""
"""
from __future__ import unicode_literals

from prompt_toolkit.eventloop.defaults import create_event_loop
from ptpython.python_input import PythonInput


def main():
    loop = create_event_loop()
    try:
        prompt = PythonInput(loop=loop)

        code_obj = prompt.app.run()
        print('You said: ' + code_obj.text)
    finally:
        loop.close()


if __name__ == '__main__':
    main()

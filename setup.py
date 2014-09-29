#!/usr/bin/env python
from setuptools import setup


setup(
        name='ptpython',
        author='Jonathan Slenders',
        version='0.1',
        url='https://github.com/jonathanslenders/ptpython',
        description='Python REPL build on top of prompt_toolkit',
        long_description='',
        install_requires = [
            'prompt_toolkit',
        ],
)

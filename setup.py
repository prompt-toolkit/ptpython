#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='ptpython',
    author='Jonathan Slenders',
    version='0.2',
    url='https://github.com/jonathanslenders/ptpython',
    description='Python REPL build on top of prompt_toolkit',
    long_description='',
    packages=find_packages('.'),
    install_requires = [
        'prompt_toolkit==0.27',
        'jedi>=0.8.1',
        'docopt',
    ],
    entry_points={
        'console_scripts': [
            'ptpython = ptpython.entry_points.run_ptpython:run',
            'ptipython = ptpython.entry_points.run_ptipython:run',
        ]
    },
    extra_require={
        'ptipython':  ['ipython'] # For ptipython, we need to have IPython
    }
)

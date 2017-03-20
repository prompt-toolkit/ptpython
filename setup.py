#!/usr/bin/env python
import os
import sys
from setuptools import setup, find_packages

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as f:
    long_description = f.read()


setup(
    name='ptpython',
    author='Jonathan Slenders',
    version='2.0.5',
    url='https://github.com/jonathanslenders/ptpython',
    description='Python REPL build on top of prompt_toolkit',
    long_description=long_description,
    packages=find_packages('.'),
    install_requires = [
        'appdirs',
        'docopt',
        'jedi>=0.9.0',
        'prompt_toolkit>=2.0.8,<2.1.0',
        'pygments',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 2',
    ],
    entry_points={
        'console_scripts': [
            'ptpython = ptpython.entry_points.run_ptpython:run',
            'ptipython = ptpython.entry_points.run_ptipython:run',
            'ptpython%s = ptpython.entry_points.run_ptpython:run' % sys.version_info[0],
            'ptpython%s.%s = ptpython.entry_points.run_ptpython:run' % sys.version_info[:2],
            'ptipython%s = ptpython.entry_points.run_ptipython:run' % sys.version_info[0],
            'ptipython%s.%s = ptpython.entry_points.run_ptipython:run' % sys.version_info[:2],
        ]
    },
    extras_require={
        'ptipython':  ['ipython'] # For ptipython, we need to have IPython
    }
)

#!/usr/bin/env python
import os
import sys
from setuptools import setup, find_packages

long_description = open(
    os.path.join(
        os.path.dirname(__file__),
        'README.rst'
    )
).read()


setup(
    name='ptpython',
    author='Jonathan Slenders',
    version='0.36',
    url='https://github.com/jonathanslenders/ptpython',
    description='Python REPL build on top of prompt_toolkit',
    long_description=long_description,
    packages=find_packages('.'),
    install_requires = [
        'docopt',
        'jedi>=0.9.0',
        'prompt_toolkit>=1.0.0,<2.0.0',
        'pygments',
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
    extra_require={
        'ptipython':  ['ipython'] # For ptipython, we need to have IPython
    }
)

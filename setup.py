#!/usr/bin/env python
import os
import sys

from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), "README.rst")) as f:
    long_description = f.read()


setup(
    name="ptpython",
    author="Jonathan Slenders",
    version="3.0.12",
    url="https://github.com/prompt-toolkit/ptpython",
    description="Python REPL build on top of prompt_toolkit",
    long_description=long_description,
    packages=find_packages("."),
    install_requires=[
        "appdirs",
        "importlib_metadata;python_version<'3.8'",
        "jedi>=0.16.0",
        # Use prompt_toolkit 3.0.11, because ptpython now runs the UI in the
        # background thread, and we need the terminal size polling that was
        # introduced here.
        "prompt_toolkit>=3.0.11,<3.1.0",
        "pygments",
        "black",
    ],
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python",
    ],
    entry_points={
        "console_scripts": [
            "ptpython = ptpython.entry_points.run_ptpython:run",
            "ptipython = ptpython.entry_points.run_ptipython:run",
            "ptpython%s = ptpython.entry_points.run_ptpython:run" % sys.version_info[0],
            "ptpython%s.%s = ptpython.entry_points.run_ptpython:run"
            % sys.version_info[:2],
            "ptipython%s = ptpython.entry_points.run_ptipython:run"
            % sys.version_info[0],
            "ptipython%s.%s = ptpython.entry_points.run_ptipython:run"
            % sys.version_info[:2],
        ]
    },
    extras_require={"ptipython": ["ipython"]},  # For ptipython, we need to have IPython
)

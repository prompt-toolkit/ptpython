#!/usr/bin/env python
import os
import sys

from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), "README.rst")) as f:
    long_description = f.read()


setup(
    name="ptpython",
    author="Jonathan Slenders",
    version="3.0.29",
    url="https://github.com/prompt-toolkit/ptpython",
    description="Python REPL build on top of prompt_toolkit",
    long_description=long_description,
    package_urls={
        "Changelog": "https://github.com/prompt-toolkit/ptpython/blob/master/CHANGELOG",
    },
    project_urls={
        "Bug Tracker": "https://github.com/prompt-toolkit/ptpython/issues",
        "Source Code": "https://github.com/prompt-toolkit/ptpython",
        "Changelog": "https://github.com/prompt-toolkit/ptpython/blob/master/CHANGELOG",
    },
    packages=find_packages("."),
    package_data={"ptpython": ["py.typed"]},
    install_requires=[
        "appdirs",
        "importlib_metadata;python_version<'3.8'",
        "jedi>=0.16.0",
        # Use prompt_toolkit 3.0.43, because of `OneStyleAndTextTuple` import.
        "prompt_toolkit>=3.0.43,<3.1.0",
        "pygments",
    ],
    python_requires=">=3.7",
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python",
    ],
    entry_points={
        "console_scripts": [
            "ptpython = ptpython.entry_points.run_ptpython:run",
            "ptipython = ptpython.entry_points.run_ptipython:run",
            f"ptpython{sys.version_info[0]} = ptpython.entry_points.run_ptpython:run",
            "ptpython{}.{} = ptpython.entry_points.run_ptpython:run".format(
                *sys.version_info[:2]
            ),
            f"ptipython{sys.version_info[0]} = ptpython.entry_points.run_ptipython:run",
            "ptipython{}.{} = ptpython.entry_points.run_ptipython:run".format(
                *sys.version_info[:2]
            ),
        ]
    },
    extras_require={
        "ptipython": ["ipython"],  # For ptipython, we need to have IPython
        "all": ["black"],  # Black not always possible on PyPy
    },
)

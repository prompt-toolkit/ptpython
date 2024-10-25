import sys

from setuptools import setup

setup(
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
    }
)

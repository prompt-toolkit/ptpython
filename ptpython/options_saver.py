"""
Restores options on startup and saves changed options on termination.
"""
from __future__ import annotations

import sys
import json
import atexit
from pathlib import Path
from functools import partial
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from python_input import PythonInput


class OptionsSaver:
    "Manages options saving and restoring"
    def __init__(self, repl: "PythonInput", filename: str) -> None:
        "Instance created at program startup"
        self.repl = repl

        # Add suffix if given file does not have one
        self.file = Path(filename)
        if not self.file.suffix:
            self.file = self.file.with_suffix(".json")

        self.file_bad = False

        # Read all stored options from file. Skip and report at
        # termination if the file is corrupt/unreadable.
        self.stored = {}
        if self.file.exists():
            try:
                with self.file.open() as fp:
                    self.stored = json.load(fp)
            except Exception:
                self.file_bad = True

        # Iterate over all options and save record of defaults and also
        # activate any saved options
        self.defaults = {}
        for category in self.repl.options:
            for option in category.options:
                field = option.field_name
                def_val, val_type = self.get_option(field)
                self.defaults[field] = def_val
                val = self.stored.get(field)
                if val is not None and val != def_val:

                    # Handle special case to convert enums from int
                    if issubclass(val_type, Enum):
                        val = list(val_type)[val]

                    # Handle special cases where a function must be
                    # called to store and enact change
                    funcs = option.get_values()
                    if isinstance(list(funcs.values())[0], partial):
                        if val_type is float:
                            val = f"{val:.2f}"
                        funcs[val]()
                    else:
                        setattr(self.repl, field, val)

        # Save changes at program exit
        atexit.register(self.save)

    def get_option(self, field: str) -> tuple[object, type]:
        "Returns option value and type for specified field"
        val = getattr(self.repl, field)
        val_type = type(val)

        # Handle special case to convert enums to int
        if issubclass(val_type, Enum):
            val = list(val_type).index(val)

        # Floats should be rounded to 2 decimal places
        if isinstance(val, float):
            val = round(val, 2)

        return val, val_type

    def save(self) -> None:
        "Save changed options to file (called once at termination)"
        # Ignore if abnormal (i.e. within exception) termination
        if sys.exc_info()[0]:
            return

        new = {}
        for category in self.repl.options:
            for option in category.options:
                field = option.field_name
                val, _ = self.get_option(field)
                if val != self.defaults[field]:
                    new[field] = val

        # Save if file will change. We only save options which are
        # different to the defaults and we always prune all other
        # options.
        if new != self.stored and not self.file_bad:
            if new:
                try:
                    self.file.parent.mkdir(parents=True, exist_ok=True)
                    with self.file.open("w") as fp:
                        json.dump(new, fp, indent=2)
                except Exception:
                    self.file_bad = True

            elif self.file.exists():
                try:
                    self.file.unlink()
                except Exception:
                    self.file_bad = True

        if self.file_bad:
            print(f"Failed to read/write file: {self.file}", file=sys.stderr)

def create(repl: "PythonInput", filename: str) -> None:
    'Create/activate the options saver'
    # Note, no need to save the instance because it is kept alive by
    # reference from atexit()
    OptionsSaver(repl, filename)

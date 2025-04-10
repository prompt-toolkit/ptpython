#!/usr/bin/env python
from __future__ import annotations

import ptpython.completer
import ptpython.eventloop
import ptpython.filters
import ptpython.history_browser
import ptpython.key_bindings
import ptpython.layout
import ptpython.python_input
import ptpython.repl
import ptpython.style
import ptpython.utils
import ptpython.validator

# For now there are no tests here.
# However this is sufficient to do at least a syntax check.


def test_dummy() -> None:
    assert ptpython.completer
    assert ptpython.eventloop
    assert ptpython.filters
    assert ptpython.history_browser
    assert ptpython.key_bindings
    assert ptpython.layout
    assert ptpython.python_input
    assert ptpython.repl
    assert ptpython.style
    assert ptpython.utils
    assert ptpython.validator

#!/usr/bin/env python
from __future__ import unicode_literals

import unittest


# For now there are no tests here.
# However this is sufficient for Travis to do at least a syntax check.
# That way we are at least sure to restrict to the Python 2.6 syntax.

import ptpython.completer
import ptpython.filters
#import ptpython.ipython
import ptpython.layout
import ptpython.python_input
import ptpython.style
import ptpython.validator
import ptpython.eventloop
import ptpython.key_bindings
import ptpython.repl
import ptpython.utils


if __name__ == '__main__':
    unittest.main()

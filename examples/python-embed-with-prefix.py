#!/usr/bin/env python
"""
Example of embedding a Python REPL, and setting a prefix before the prompt.
"""
from __future__ import unicode_literals

from ptpython.repl import embed
from pygments.token import Token


def configure(repl):
    repl.get_prompt_prefix = lambda: [(Token.In, '[hello] ')]


def main():
    embed(globals(), locals(), configure=configure)


if __name__ == '__main__':
    main()

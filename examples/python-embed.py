#!/usr/bin/env python
"""
"""
from ptpython.repl import embed


def main() -> None:
    embed(globals(), locals(), vi_mode=False)


if __name__ == "__main__":
    main()

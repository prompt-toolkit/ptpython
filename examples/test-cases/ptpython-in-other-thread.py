#!/usr/bin/env python
"""
Example of running ptpython in another thread.

(For testing whether it's working fine if it's not embedded in the main
thread.)
"""
import threading

from ptpython.repl import embed


def in_thread():
    embed(globals(), locals(), vi_mode=False)


def main():
    th = threading.Thread(target=in_thread)
    th.start()
    th.join()


if __name__ == "__main__":
    main()

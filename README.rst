ptpython
========

*A better Python REPL*

::

    pip install ptpython

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/example1.png

|Build Status|

Ptpython is an advanced Python REPL. It should work on all
Python versions from 2.6 up to 3.5 and work cross platform (Linux,
BSD, OS X and Windows).


Installation
************

Install it using pip:

::

    pip install ptpython

Start it by typing ``ptpython``.


Features
********

- Syntax highlighting.
- Multiline editing (the up arrow works).
- Autocompletion.
- Mouse support. [1]
- Support for color schemes.
- Support for `bracketed paste <https://cirw.in/blog/bracketed-paste>`_ [2].
- Both Vi and Emacs key bindings.
- Support for double width (Chinese) characters.
- ... and many other stuff.


[1] Disabled by default. (Enable in the menu.)

[2] If the terminal supports it (most terminals do), this allows pasting
without going into paste mode. It will keep the indentation.


More screenshots
****************

The configuration menu:

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/ptpython-menu.png

The history page and its help:

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/ptpython-history-help.png

Autocompletion:

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/file-completion.png


Embedding the REPL
******************

Embedding the REPL in any Python application is easy:

.. code:: python

    from ptpython.repl import embed
    embed(globals(), locals())


Multiline editing
*****************

Multi-line editing mode will automatically turn on when you press enter after a
colon.

To execute the input in multi-line mode, you can either press ``Alt+Enter``, or
``Esc`` followed by ``Enter``. (If you want the first to work in the OS X
terminal, you have to check the "Use option as meta key" checkbox in your
terminal settings. For iTerm2, you have to check "Left option acts as +Esc" in
the options.)

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/multiline.png


Syntax validation
*****************

Before execution, ``ptpython`` will see whether the input is syntactically
correct Python code. If not, it will show a warning, and move the cursor to the
error.

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/validation.png


Additional features
*******************

Running system commands: Press ``Meta-!`` in Emacs mode or just ``!`` in Vi
navigation mode to see the "Shell command" prompt. There you can enter system
commands without leaving the REPL.

Selecting text: Press ``Control+Space`` in Emacs mode on ``V`` (major V) in Vi
navigation mode.


Configuration
*************

It is possible to create a ``~/.ptpython/config.py`` file to customize the configuration.

Have a look at this example to see what is possible:
`config.py <https://github.com/jonathanslenders/ptpython/blob/master/examples/ptpython_config/config.py>`_


IPython support
***************

Run ``ptipython`` (prompt_toolkit - IPython), to get a nice interactive shell
with all the power that IPython has to offer, like magic functions and shell
integration. Make sure that IPython has been installed. (``pip install
ipython``)

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/ipython.png


Django support
**************

`django-extensions <https://github.com/django-extensions/django-extensions>`_
has a ``shell_plus`` management command. When ``ptpython`` has been installed,
it will by default use ``ptpython`` or ``ptipython``.


PDB
***

There is an experimental PDB replacement: `ptpdb
<https://github.com/jonathanslenders/ptpdb>`_.


Windows support
***************

``prompt_toolkit`` and ``ptpython`` works better on Linux and OS X than on
Windows. Some things might not work, but it is usable:

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/windows.png


FAQ
***

**Q**: The ``Ctrl-S`` forward search doesn't work and freezes my terminal.

**A**: Try to run ``stty -ixon`` in your terminal to disable flow control.

**Q**: The ``Meta``-key doesn't work.

**A**: For some terminals you have to enable the Alt-key to act as meta key, but you 
can also type ``Escape`` before any key instead.


Alternatives
************

- `BPython <http://bpython-interpreter.org/downloads.html>`_
- `IPython <https://ipython.org/>`_

If you find another alternative, you can create an issue and we'll list it
here. If you find a nice feature somewhere that is missing in ``ptpython``,
also create a GitHub issue and maybe we'll implement it.


Special thanks to
*****************

- `Pygments <http://pygments.org/>`_: Syntax highlighter.
- `Jedi <http://jedi.jedidjah.ch/en/latest/>`_: Autocompletion library.
- `Docopt <http://docopt.org/>`_: Command-line interface description language.
- `wcwidth <https://github.com/jquast/wcwidth>`_: Determine columns needed for a wide characters.
- `prompt_toolkit <http://github.com/jonathanslenders/python-prompt-toolkit>`_ for the interface.

.. |Build Status| image:: https://api.travis-ci.org/jonathanslenders/ptpython.svg?branch=master
    :target: https://travis-ci.org/jonathanslenders/ptpython#

.. |PyPI| image:: https://pypip.in/version/prompt-toolkit/badge.svg
    :target: https://pypi.python.org/pypi/prompt-toolkit/
    :alt: Latest Version

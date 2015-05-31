ptpython: a better Python REPL
==============================

.. image:: https://pypip.in/version/ptpython/badge.svg
    :target: https://pypi.python.org/pypi/ptpython/
    :alt: Latest Version

``ptpython`` is an advanced Python REPL built on top of the `prompt_toolkit
<http://github.com/jonathanslenders/python-prompt-toolkit>`_ library.

It works best on all Posix systems like Linux, BSD and OS X. But it should work
as well on Windows. It works on all Python versions from 2.6 up to 3.4.


Installation
************

To install ``ptpython``, type:

::

    pip install ptpython


The REPL
********

Run ``ptpython`` to get an interactive Python prompt with syntax highlighting,
code completion, etc...

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/example1.png

By default, you will have Emacs key bindings, but if you prefer Vi bindings
(like in the above screenshot) then run ``ptpython --vi``.

If you want to embed the REPL inside your application at one point, do:

.. code:: python

    from ptpython.repl import embed
    embed(globals(), locals())


Autocompletion
**************

``Tab`` and ``shift+tab`` complete the input.
In Vi-mode, you can also use ``Ctrl+N`` and ``Ctrl+P``.

There is even completion on file names inside strings:

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/file-completion.png


Multiline editing
*****************

Usually, multi-line editing mode will automatically turn on when you press enter
after a colon, however you can always turn it on by pressing ``F7``.

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


Other features
**************

Running system commands: Press ``Meta-!`` in Emacs mode or just ``!`` in Vi
navigation mode to see the "Shell command" prompt. There you can enter system
commands without leaving the REPL.

Selecting text: Press ``Control+Space`` in Emacs mode on ``V`` (major V) in Vi
navigation mode.


Configurating
*************

It is possible to create a ``~/.ptpython/config.py`` file to customize the configuration.

Have a look at this example to see what is possible:
`config.py <https://github.com/jonathanslenders/ptpython/blob/master/examples/ptpython_config/config.py>`_


You love IPython?
*****************

Run ``ptipython`` (prompt_toolkit - IPython), to get a nice interactive shell
with all the power that IPython has to offer, like magic functions and shell
integration. Make sure that IPython has been installed. (``pip install
ipython``)

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/ipython.png


You are using Django?
*********************

`django-extensions <https://github.com/django-extensions/django-extensions>`_
has a ``shell_plus`` management command. When ``ptpython`` has been installed,
it will by default use ``ptpython`` or ``ptipython``.


PDB
***

There is an experimental PDB replacement: `ptpdb
<https://github.com/jonathanslenders/ptpdb>`_.


About Windows support
*********************

``prompt_toolkit`` works still a little better on systems like Linux and OS X
than on Windows, but it certainly is usable. One thing that still needs
attention is the colorscheme. Windows terminals don't support all colors, so we
have to create another colorscheme for Windows.

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/windows.png


FAQ
---

Q
 The ``Ctrl-S`` forward search doesn't work and freezes my terminal.
A
 Try to run ``stty -ixon`` in your terminal to disable flow control.

Q
 The ``Meta``-key doesn't work.
A
 For some terminals you have to enable the Alt-key to act as meta key, but you
 can also type ``Escape`` before any key instead.


Alternatives
************

Have a look at the alternatives.

- `BPython <http://bpython-interpreter.org/downloads.html>`_

If you find another alternative, you can create an issue and we'll list it
here. If you find a nice feature somewhere that is missing in ``ptpython``,
also create a GitHub issue and mabye we'll implement it.


Special thanks to
*****************

- `Pygments <http://pygments.org/>`_: Syntax highlighter.
- `Jedi <http://jedi.jedidjah.ch/en/latest/>`_: Autocompletion library.
- `Docopt <http://docopt.org/>`_: Command-line interface description language.
- `wcwidth <https://github.com/jquast/wcwidth>`_: Determine columns needed for a wide characters.
- `prompt_toolkit <http://github.com/jonathanslenders/python-prompt-toolkit>`_ for the interface.

.. |PyPI| image:: https://pypip.in/version/prompt-toolkit/badge.svg
    :target: https://pypi.python.org/pypi/prompt-toolkit/
    :alt: Latest Version

ptpython
========

|Build Status|  |PyPI|  |License|

*A better Python REPL*

::

    pip install ptpython

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/example1.png

Ptpython is an advanced Python REPL. It should work on all
Python versions from 2.6 up to 3.9 and work cross platform (Linux,
BSD, OS X and Windows).

Note: this version of ptpython requires at least Python 3.6. Install ptpython
2.0.5 for older Python versions.


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
- ... and many other things.


[1] Disabled by default. (Enable in the menu.)

[2] If the terminal supports it (most terminals do), this allows pasting
without going into paste mode. It will keep the indentation.

__pt_repr__: A nicer repr with colors
*************************************

When classes implement a ``__pt_repr__`` method, this will be used instead of
``__repr__`` for printing. Any `prompt_toolkit "formatted text"
<https://python-prompt-toolkit.readthedocs.io/en/master/pages/printing_text.html>`_
can be returned from here. In order to avoid writing a ``__repr__`` as well,
the ``ptpython.utils.ptrepr_to_repr`` decorator can be applied. For instance:

.. code:: python

    from ptpython.utils import ptrepr_to_repr
    from prompt_toolkit.formatted_text import HTML

    @ptrepr_to_repr
    class MyClass:
        def __pt_repr__(self):
            return HTML('<yellow>Hello world!</yellow>')

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

You can make ptpython your default Python REPL by creating a `PYTHONSTARTUP file
<https://docs.python.org/3/tutorial/appendix.html#the-interactive-startup-file>`_ containing code
like this:

.. code:: python

   import sys
   try:
       from ptpython.repl import embed
   except ImportError:
       print("ptpython is not available: falling back to standard prompt")
   else:
       sys.exit(embed(globals(), locals()))


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

Selecting text: Press ``Control+Space`` in Emacs mode or ``V`` (major V) in Vi
navigation mode.


Configuration
*************

It is possible to create a ``config.py`` file to customize configuration.
ptpython will look in an appropriate platform-specific directory via `appdirs
<https://pypi.org/project/appdirs/>`. See the ``appdirs`` documentation for the
precise location for your platform. A ``PTPYTHON_CONFIG_HOME`` environment
variable, if set, can also be used to explicitly override where configuration
is looked for.

Have a look at this example to see what is possible:
`config.py <https://github.com/jonathanslenders/ptpython/blob/master/examples/ptpython_config/config.py>`_


IPython support
***************

Run ``ptipython`` (prompt_toolkit - IPython), to get a nice interactive shell
with all the power that IPython has to offer, like magic functions and shell
integration. Make sure that IPython has been installed. (``pip install
ipython``)

.. image :: https://github.com/jonathanslenders/ptpython/raw/master/docs/images/ipython.png

This is also available for embedding:

.. code:: python

    from ptpython.ipython.repl import embed
    embed(globals(), locals())


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
- `wcwidth <https://github.com/jquast/wcwidth>`_: Determine columns needed for a wide characters.
- `prompt_toolkit <http://github.com/jonathanslenders/python-prompt-toolkit>`_ for the interface.

.. |Build Status| image:: https://api.travis-ci.org/prompt-toolkit/ptpython.svg?branch=master
    :target: https://travis-ci.org/prompt-toolkit/ptpython#

.. |License| image:: https://img.shields.io/github/license/prompt-toolkit/ptpython.svg
    :target: https://github.com/prompt-toolkit/ptpython/blob/master/LICENSE

.. |PyPI| image:: https://pypip.in/version/ptpython/badge.svg
    :target: https://pypi.python.org/pypi/ptpython/
    :alt: Latest Version

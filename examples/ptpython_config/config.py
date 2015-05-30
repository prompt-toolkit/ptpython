"""
Configuration example for ``ptpython``.

Copy this file to ~/.ptpython/config.py
"""
from __future__ import unicode_literals
from prompt_toolkit.keys import Keys

__all__ = (
    'configure',
)


def configure(repl):
    """
    Configuration method. This is called during the start-up of ptpython.

    :param repl: `PythonRepl` instance.
    """
    # Show sidebar (bool).
    repl.show_sidebar = False

    # Show function signature (bool).
    repl.show_signature = True

    # Show docstring (bool).
    repl.show_docstring = False

    # Show completions.
    repl.show_completions_menu = True
    repl.show_completions_toolbar = False

    # Show line numbers (when the input contains multiple lines.)
    repl.show_line_numbers = True

    # Show status bar.
    repl.show_status_bar = True

    # Complete while typing. (Don't require tab before the
    # completion menu is shown.)
    repl.complete_while_typing = True

    # Vi mode.
    repl.vi_mode = False

    # Paste mode. (When True, don't insert whitespace after new line.)
    repl.paste_mode = False

    # Enable open-in-editor. Pressing C-X C-E in emacs mode or 'v' in
    # Vi navigation mode will open the input in the current editor.
    repl.enable_open_in_editor = True

    # Enable system prompt. Pressing meta-! will display the system prompt.
    repl.enable_system_prompt = True

    # Add custom key binding for PDB.
    @repl.add_key_binding(Keys.ControlB)
    def _(event):
        ' Pressing Control-B will insert "pdb.set_trace()" '
        event.cli.current_buffer.insert_text('\nimport pdb; pdb.set_trace()\n')

    # Custom key binding for some simple autocorrection while typing.
    corrections = {
        'impotr': 'import',
        'pritn': 'print',
    }

    @repl.add_key_binding(' ')
    def _(event):
        ' When a space is pressed. Check & correct word before cursor. '
        b = event.cli.current_buffer
        w = b.document.get_word_before_cursor()

        if w is not None:
            if w in corrections:
                b.delete_before_cursor(count=len(w))
                b.insert_text(corrections[w])

        b.insert_text(' ')

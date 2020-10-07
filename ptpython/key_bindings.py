from prompt_toolkit.application import get_app
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import (
    Condition,
    emacs_insert_mode,
    emacs_mode,
    has_focus,
    has_selection,
    vi_insert_mode,
)
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.key_binding.bindings import named_commands as nc

from .utils import document_is_multiline_python

__all__ = [
    "load_python_bindings",
    "load_sidebar_bindings",
    "load_confirm_exit_bindings",
]


@Condition
def tab_should_insert_whitespace():
    """
    When the 'tab' key is pressed with only whitespace character before the
    cursor, do autocompletion. Otherwise, insert indentation.

    Except for the first character at the first line. Then always do a
    completion. It doesn't make sense to start the first line with
    indentation.
    """
    b = get_app().current_buffer
    before_cursor = b.document.current_line_before_cursor

    return bool(b.text and (not before_cursor or before_cursor.isspace()))


def load_python_bindings(python_input):
    """
    Custom key bindings.
    """
    bindings = KeyBindings()

    sidebar_visible = Condition(lambda: python_input.show_sidebar)
    handle = bindings.add

    @handle("c-l")
    def _(event):
        """
        Clear whole screen and render again -- also when the sidebar is visible.
        """
        event.app.renderer.clear()

    @handle("c-z")
    def _(event):
        """
        Suspend.
        """
        if python_input.enable_system_bindings:
            event.app.suspend_to_background()

    @handle("f2")
    def _(event):
        """
        Show/hide sidebar.
        """
        python_input.show_sidebar = not python_input.show_sidebar
        if python_input.show_sidebar:
            event.app.layout.focus(python_input.ptpython_layout.sidebar)
        else:
            event.app.layout.focus_last()

    @handle("f3")
    def _(event):
        """
        Select from the history.
        """
        python_input.enter_history()

    @handle("f4")
    def _(event):
        """
        Toggle between Vi and Emacs mode.
        """
        python_input.vi_mode = not python_input.vi_mode

    @handle("f6")
    def _(event):
        """
        Enable/Disable paste mode.
        """
        python_input.paste_mode = not python_input.paste_mode

    @handle(
        "tab", filter=~sidebar_visible & ~has_selection & tab_should_insert_whitespace
    )
    def _(event):
        """
        When tab should insert whitespace, do that instead of completion.
        """
        event.app.current_buffer.insert_text("    ")

    @Condition
    def is_multiline():
        return document_is_multiline_python(python_input.default_buffer.document)

    @handle(
        "enter",
        filter=~sidebar_visible
        & ~has_selection
        & (vi_insert_mode | emacs_insert_mode)
        & has_focus(DEFAULT_BUFFER)
        & ~is_multiline,
    )
    @handle(Keys.Escape, Keys.Enter, filter=~sidebar_visible & emacs_mode)
    def _(event):
        """
        Accept input (for single line input).
        """
        b = event.current_buffer

        if b.validate():
            # When the cursor is at the end, and we have an empty line:
            # drop the empty lines, but return the value.
            b.document = Document(
                text=b.text.rstrip(), cursor_position=len(b.text.rstrip())
            )

            b.validate_and_handle()

    @handle(
        "enter",
        filter=~sidebar_visible
        & ~has_selection
        & (vi_insert_mode | emacs_insert_mode)
        & has_focus(DEFAULT_BUFFER)
        & is_multiline,
    )
    def _(event):
        """
        Behaviour of the Enter key.

        Auto indent after newline/Enter.
        (When not in Vi navigaton mode, and when multiline is enabled.)
        """
        b = event.current_buffer
        empty_lines_required = python_input.accept_input_on_enter or 10000

        def at_the_end(b):
            """we consider the cursor at the end when there is no text after
            the cursor, or only whitespace."""
            text = b.document.text_after_cursor
            return text == "" or (text.isspace() and not "\n" in text)

        if python_input.paste_mode:
            # In paste mode, always insert text.
            b.insert_text("\n")

        elif at_the_end(b) and b.document.text.replace(" ", "").endswith(
            "\n" * (empty_lines_required - 1)
        ):
            # When the cursor is at the end, and we have an empty line:
            # drop the empty lines, but return the value.
            if b.validate():
                b.document = Document(
                    text=b.text.rstrip(), cursor_position=len(b.text.rstrip())
                )

                b.validate_and_handle()
        else:
            auto_newline(b)

    @handle(
        "c-d",
        filter=~sidebar_visible
        & has_focus(python_input.default_buffer)
        & Condition(
            lambda:
            # The current buffer is empty.
            not get_app().current_buffer.text
        ),
    )
    def _(event):
        """
        Override Control-D exit, to ask for confirmation.
        """
        if python_input.confirm_exit:
            # Show exit confirmation and focus it (focusing is important for
            # making sure the default buffer key bindings are not active).
            python_input.show_exit_confirmation = True
            python_input.app.layout.focus(
                python_input.ptpython_layout.exit_confirmation
            )
        else:
            event.app.exit(exception=EOFError)

    @handle("c-c", filter=has_focus(python_input.default_buffer))
    def _(event):
        " Abort when Control-C has been pressed. "
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    return bindings


def load_sidebar_bindings(python_input):
    """
    Load bindings for the navigation in the sidebar.
    """
    bindings = KeyBindings()

    handle = bindings.add
    sidebar_visible = Condition(lambda: python_input.show_sidebar)

    @handle("up", filter=sidebar_visible)
    @handle("c-p", filter=sidebar_visible)
    @handle("k", filter=sidebar_visible)
    def _(event):
        " Go to previous option. "
        python_input.selected_option_index = (
            python_input.selected_option_index - 1
        ) % python_input.option_count

    @handle("down", filter=sidebar_visible)
    @handle("c-n", filter=sidebar_visible)
    @handle("j", filter=sidebar_visible)
    def _(event):
        " Go to next option. "
        python_input.selected_option_index = (
            python_input.selected_option_index + 1
        ) % python_input.option_count

    @handle("right", filter=sidebar_visible)
    @handle("l", filter=sidebar_visible)
    @handle(" ", filter=sidebar_visible)
    def _(event):
        " Select next value for current option. "
        option = python_input.selected_option
        option.activate_next()

    @handle("left", filter=sidebar_visible)
    @handle("h", filter=sidebar_visible)
    def _(event):
        " Select previous value for current option. "
        option = python_input.selected_option
        option.activate_previous()

    @handle("c-c", filter=sidebar_visible)
    @handle("c-d", filter=sidebar_visible)
    @handle("c-d", filter=sidebar_visible)
    @handle("enter", filter=sidebar_visible)
    @handle("escape", filter=sidebar_visible)
    def _(event):
        " Hide sidebar. "
        python_input.show_sidebar = False
        event.app.layout.focus_last()

    @Condition
    def ebivim():
        return python_input.emacs_bindings_in_vi_insert_mode

    focused_insert = has_focus(DEFAULT_BUFFER) & vi_insert_mode

    # Needed for to accept autosuggestions in vi insert mode
    @handle("c-e", filter=focused_insert & ebivim)
    def _(event):
        b = event.current_buffer
        suggestion = b.suggestion
        if suggestion:
            b.insert_text(suggestion.text)
        else:
            nc.end_of_line(event)

    @handle("c-f", filter=focused_insert & ebivim)
    def _(event):
        b = event.current_buffer
        suggestion = b.suggestion
        if suggestion:
            b.insert_text(suggestion.text)
        else:
            nc.forward_char(event)

    @handle("escape", "f", filter=focused_insert & ebivim)
    def _(event):
        b = event.current_buffer
        suggestion = b.suggestion
        if suggestion:
            t = re.split(r"(\S+\s+)", suggestion.text)
            b.insert_text(next((x for x in t if x), ""))
        else:
            nc.forward_word(event)

    # Simple Control keybindings
    key_cmd_dict = {
        "c-a": nc.beginning_of_line,
        "c-b": nc.backward_char,
        "c-k": nc.kill_line,
        "c-w": nc.backward_kill_word,
        "c-y": nc.yank,
        "c-_": nc.undo,
    }

    for key, cmd in key_cmd_dict.items():
        handle(key, filter=focused_insert & ebivim)(cmd)

    # Alt and Combo Control keybindings
    keys_cmd_dict = {
        # Control Combos
        ("c-x", "c-e"): nc.edit_and_execute,
        ("c-x", "e"): nc.edit_and_execute,
        # Alt
        ("escape", "b"): nc.backward_word,
        ("escape", "c"): nc.capitalize_word,
        ("escape", "d"): nc.kill_word,
        ("escape", "h"): nc.backward_kill_word,
        ("escape", "l"): nc.downcase_word,
        ("escape", "u"): nc.uppercase_word,
        ("escape", "y"): nc.yank_pop,
        ("escape", "."): nc.yank_last_arg,
    }

    for keys, cmd in keys_cmd_dict.items():
        handle(*keys, filter=focused_insert & ebivim)(cmd)

    return bindings


def load_confirm_exit_bindings(python_input):
    """
    Handle yes/no key presses when the exit confirmation is shown.
    """
    bindings = KeyBindings()

    handle = bindings.add
    confirmation_visible = Condition(lambda: python_input.show_exit_confirmation)

    @handle("y", filter=confirmation_visible)
    @handle("Y", filter=confirmation_visible)
    @handle("enter", filter=confirmation_visible)
    @handle("c-d", filter=confirmation_visible)
    def _(event):
        """
        Really quit.
        """
        event.app.exit(exception=EOFError, style="class:exiting")

    @handle(Keys.Any, filter=confirmation_visible)
    def _(event):
        """
        Cancel exit.
        """
        python_input.show_exit_confirmation = False
        python_input.app.layout.focus_previous()

    return bindings


def auto_newline(buffer):
    r"""
    Insert \n at the cursor position. Also add necessary padding.
    """
    insert_text = buffer.insert_text

    if buffer.document.current_line_after_cursor:
        # When we are in the middle of a line. Always insert a newline.
        insert_text("\n")
    else:
        # Go to new line, but also add indentation.
        current_line = buffer.document.current_line_before_cursor.rstrip()
        insert_text("\n")

        # Unident if the last line ends with 'pass', remove four spaces.
        unindent = current_line.rstrip().endswith(" pass")

        # Copy whitespace from current line
        current_line2 = current_line[4:] if unindent else current_line

        for c in current_line2:
            if c.isspace():
                insert_text(c)
            else:
                break

        # If the last line ends with a colon, add four extra spaces.
        if current_line[-1:] == ":":
            for x in range(4):
                insert_text(" ")

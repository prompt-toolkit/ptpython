from __future__ import unicode_literals

from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import HasSelection, HasFocus, Condition, ViInsertMode, EmacsInsertMode, EmacsMode
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from .utils import document_is_multiline_python

__all__ = (
    'load_python_bindings',
    'load_sidebar_bindings',
    'load_confirm_exit_bindings',
)


@Condition
def tab_should_insert_whitespace(app):
    """
    When the 'tab' key is pressed with only whitespace character before the
    cursor, do autocompletion. Otherwise, insert indentation.

    Except for the first character at the first line. Then always do a
    completion. It doesn't make sense to start the first line with
    indentation.
    """
    b = app.current_buffer
    before_cursor = b.document.current_line_before_cursor

    return bool(b.text and (not before_cursor or before_cursor.isspace()))


def load_python_bindings(python_input):
    """
    Custom key bindings.
    """
    bindings = KeyBindings()

    sidebar_visible = Condition(lambda app: python_input.show_sidebar)
    handle = bindings.add
    has_selection = HasSelection()

    @handle(Keys.ControlL)
    def _(event):
        """
        Clear whole screen and render again -- also when the sidebar is visible.
        """
        event.app.renderer.clear()

    @handle(Keys.F2)
    def _(event):
        """
        Show/hide sidebar.
        """
        python_input.show_sidebar = not python_input.show_sidebar

    @handle(Keys.F3)
    def _(event):
        """
        Select from the history.
        """
        python_input.enter_history(event.app)

    @handle(Keys.F4)
    def _(event):
        """
        Toggle between Vi and Emacs mode.
        """
        python_input.vi_mode = not python_input.vi_mode

    @handle(Keys.F6)
    def _(event):
        """
        Enable/Disable paste mode.
        """
        python_input.paste_mode = not python_input.paste_mode

    @handle(Keys.Tab, filter= ~sidebar_visible & ~has_selection & tab_should_insert_whitespace)
    def _(event):
        """
        When tab should insert whitespace, do that instead of completion.
        """
        event.app.current_buffer.insert_text('    ')

    @Condition
    def is_multiline(app):
        return document_is_multiline_python(python_input.default_buffer.document)

    @handle(Keys.Enter, filter= ~sidebar_visible & ~has_selection &
            (ViInsertMode() | EmacsInsertMode()) &
            HasFocus(DEFAULT_BUFFER) & ~is_multiline)
    @handle(Keys.Escape, Keys.Enter, filter= ~sidebar_visible & EmacsMode())
    def _(event):
        """
        Accept input (for single line input).
        """
        b = event.current_buffer

        if b.validate():
            # When the cursor is at the end, and we have an empty line:
            # drop the empty lines, but return the value.

            b.document = Document(
                text=b.text.rstrip(),
                cursor_position=len(b.text.rstrip()))

            b.validate_and_handle(event.app)

    @handle(Keys.Enter, filter= ~sidebar_visible & ~has_selection &
            (ViInsertMode() | EmacsInsertMode()) &
            HasFocus(DEFAULT_BUFFER) & is_multiline)
    def _(event):
        """
        Behaviour of the Enter key.

        Auto indent after newline/Enter.
        (When not in Vi navigaton mode, and when multiline is enabled.)
        """
        b = event.current_buffer
        empty_lines_required = python_input.accept_input_on_enter or 10000

        def at_the_end(b):
            """ we consider the cursor at the end when there is no text after
            the cursor, or only whitespace. """
            text = b.document.text_after_cursor
            return text == '' or (text.isspace() and not '\n' in text)

        if python_input.paste_mode:
            # In paste mode, always insert text.
            b.insert_text('\n')

        elif at_the_end(b) and b.document.text.replace(' ', '').endswith(
                    '\n' * (empty_lines_required - 1)):
            if b.validate():
                # When the cursor is at the end, and we have an empty line:
                # drop the empty lines, but return the value.
                b.document = Document(
                    text=b.text.rstrip(),
                    cursor_position=len(b.text.rstrip()))

                b.validate_and_handle(event.app)
        else:
            auto_newline(b)

    @handle(Keys.ControlD, filter=~sidebar_visible & Condition(lambda app:
            # Only when the `confirm_exit` flag is set.
            python_input.confirm_exit and
            # And the current buffer is empty.
            app.current_buffer == python_input.default_buffer and
            not app.current_buffer.text))
    def _(event):
        """
        Override Control-D exit, to ask for confirmation.
        """
        python_input.show_exit_confirmation = True

    return bindings


def load_sidebar_bindings(python_input):
    """
    Load bindings for the navigation in the sidebar.
    """
    bindings = KeyBindings()

    handle = bindings.add
    sidebar_visible = Condition(lambda app: python_input.show_sidebar)

    @handle(Keys.Up, filter=sidebar_visible)
    @handle(Keys.ControlP, filter=sidebar_visible)
    @handle('k', filter=sidebar_visible)
    def _(event):
        " Go to previous option. "
        python_input.selected_option_index = (
            (python_input.selected_option_index - 1) % python_input.option_count)

    @handle(Keys.Down, filter=sidebar_visible)
    @handle(Keys.ControlN, filter=sidebar_visible)
    @handle('j', filter=sidebar_visible)
    def _(event):
        " Go to next option. "
        python_input.selected_option_index = (
            (python_input.selected_option_index + 1) % python_input.option_count)

    @handle(Keys.Right, filter=sidebar_visible)
    @handle('l', filter=sidebar_visible)
    @handle(' ', filter=sidebar_visible)
    def _(event):
        " Select next value for current option. "
        option = python_input.selected_option
        option.activate_next()

    @handle(Keys.Left, filter=sidebar_visible)
    @handle('h', filter=sidebar_visible)
    def _(event):
        " Select previous value for current option. "
        option = python_input.selected_option
        option.activate_previous()

    @handle(Keys.ControlC, filter=sidebar_visible)
    @handle(Keys.ControlG, filter=sidebar_visible)
    @handle(Keys.ControlD, filter=sidebar_visible)
    @handle(Keys.Enter, filter=sidebar_visible)
    @handle(Keys.Escape, filter=sidebar_visible)
    def _(event):
        " Hide sidebar. "
        python_input.show_sidebar = False

    return bindings


def load_confirm_exit_bindings(python_input):
    """
    Handle yes/no key presses when the exit confirmation is shown.
    """
    bindings = KeyBindings()

    handle = bindings.add
    confirmation_visible = Condition(lambda app: python_input.show_exit_confirmation)

    @handle('y', filter=confirmation_visible)
    @handle('Y', filter=confirmation_visible)
    @handle(Keys.Enter, filter=confirmation_visible)
    @handle(Keys.ControlD, filter=confirmation_visible)
    def _(event):
        """
        Really quit.
        """
        event.app.exit()

    @handle(Keys.Any, filter=confirmation_visible)
    def _(event):
        """
        Cancel exit.
        """
        python_input.show_exit_confirmation = False

    return bindings


def auto_newline(buffer):
    r"""
    Insert \n at the cursor position. Also add necessary padding.
    """
    insert_text = buffer.insert_text

    if buffer.document.current_line_after_cursor:
        # When we are in the middle of a line. Always insert a newline.
        insert_text('\n')
    else:
        # Go to new line, but also add indentation.
        current_line = buffer.document.current_line_before_cursor.rstrip()
        insert_text('\n')

        # Unident if the last line ends with 'pass', remove four spaces.
        unindent = current_line.rstrip().endswith(' pass')

        # Copy whitespace from current line
        current_line2 = current_line[4:] if unindent else current_line

        for c in current_line2:
            if c.isspace():
                insert_text(c)
            else:
                break

        # If the last line ends with a colon, add four extra spaces.
        if current_line[-1:] == ':':
            for x in range(4):
                insert_text(' ')

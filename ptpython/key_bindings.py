from __future__ import unicode_literals

from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import HasSelection, IsMultiline, Filter, HasFocus, Condition, ViInsertMode, EmacsInsertMode
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.keys import Keys

__all__ = (
    'load_python_bindings',
    'load_sidebar_bindings',
    'load_confirm_exit_bindings',
)


class TabShouldInsertWhitespaceFilter(Filter):
    """
    When the 'tab' key is pressed with only whitespace character before the
    cursor, do autocompletion. Otherwise, insert indentation.

    Except for the first character at the first line. Then always do a
    completion. It doesn't make sense to start the first line with
    indentation.
    """
    def __call__(self, cli):
        b = cli.current_buffer
        before_cursor = b.document.current_line_before_cursor

        return bool(b.text and (not before_cursor or before_cursor.isspace()))


def load_python_bindings(key_bindings_manager, python_input):
    """
    Custom key bindings.
    """
    sidebar_visible = Condition(lambda cli: python_input.show_sidebar)
    handle = key_bindings_manager.registry.add_binding
    has_selection = HasSelection()
    vi_mode_enabled = Condition(lambda cli: python_input.vi_mode)

    @handle(Keys.ControlL)
    def _(event):
        """
        Clear whole screen and render again -- also when the sidebar is visible.
        """
        event.cli.renderer.clear()

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
        python_input.enter_history(event.cli)

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

    @handle(Keys.Tab, filter= ~sidebar_visible & ~has_selection & TabShouldInsertWhitespaceFilter())
    def _(event):
        """
        When tab should insert whitespace, do that instead of completion.
        """
        event.cli.current_buffer.insert_text('    ')

    @handle(Keys.ControlJ, filter= ~sidebar_visible & ~has_selection &
            (ViInsertMode() | EmacsInsertMode()) &
            HasFocus(DEFAULT_BUFFER) & IsMultiline())
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

                b.accept_action.validate_and_handle(event.cli, b)
        else:
            auto_newline(b)

    @handle(Keys.ControlD, filter=~sidebar_visible & Condition(lambda cli:
            # Only when the `confirm_exit` flag is set.
            python_input.confirm_exit and
            # And the current buffer is empty.
            cli.current_buffer_name == DEFAULT_BUFFER and
            not cli.current_buffer.text))
    def _(event):
        """
        Override Control-D exit, to ask for confirmation.
        """
        python_input.show_exit_confirmation = True


def load_sidebar_bindings(key_bindings_manager, python_input):
    """
    Load bindings for the navigation in the sidebar.
    """
    handle = key_bindings_manager.registry.add_binding
    sidebar_visible = Condition(lambda cli: python_input.show_sidebar)

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
    @handle(Keys.ControlJ, filter=sidebar_visible)
    @handle(Keys.Escape, filter=sidebar_visible)
    def _(event):
        " Hide sidebar. "
        python_input.show_sidebar = False


def load_confirm_exit_bindings(key_bindings_manager, python_input):
    """
    Handle yes/no key presses when the exit confirmation is shown.
    """
    handle = key_bindings_manager.registry.add_binding
    confirmation_visible = Condition(lambda cli: python_input.show_exit_confirmation)

    @handle('y', filter=confirmation_visible)
    @handle('Y', filter=confirmation_visible)
    @handle(Keys.ControlJ, filter=confirmation_visible)
    def _(event):
        """
        Really quit.
        """
        event.cli.exit()

    @handle(Keys.Any, filter=confirmation_visible)
    def _(event):
        """
        Cancel exit.
        """
        python_input.show_exit_confirmation = False


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

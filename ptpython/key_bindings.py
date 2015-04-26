from __future__ import unicode_literals

from prompt_toolkit.document import Document
from prompt_toolkit.filters import HasSelection, IsMultiline, Filter, HasFocus
from prompt_toolkit.key_binding.bindings.vi import ViStateFilter
from prompt_toolkit.key_binding.manager import ViModeEnabled
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.keys import Keys

__all__ = (
    'load_python_bindings',
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


def load_python_bindings(key_bindings_manager, settings):
    """
    Custom key bindings.
    """
    handle = key_bindings_manager.registry.add_binding
    has_selection = HasSelection()

    @handle(Keys.F2)
    def _(event):
        """
        Show/hide sidebar.
        """
        settings.show_sidebar = not settings.show_sidebar

    @handle(Keys.F3)
    def _(event):
        """
        Shange completion style.
        """
        # Toggle between combinations.
        settings.show_completions_toolbar, settings.show_completions_menu = {
            (False, False): (False, True),
            (False, True): (True, False),
            (True, False): (False, False),
        }[settings.show_completions_toolbar, settings.show_completions_menu]

    @handle(Keys.F4)
    def _(event):
        """
        Toggle between Vi and Emacs mode.
        """
        key_bindings_manager.enable_vi_mode = not key_bindings_manager.enable_vi_mode

    @handle(Keys.F5)
    def _(event):
        """
        Enable/Disable complete while typing.
        """
        settings.complete_while_typing = not settings.complete_while_typing

    @handle(Keys.F6)
    def _(event):
        """
        Enable/Disable paste mode.
        """
        settings.paste_mode = not settings.paste_mode

    @handle(Keys.F8)
    def _(event):
        """
        Show/hide signature.
        """
        settings.show_signature = not settings.show_signature

    @handle(Keys.F9)
    def _(event):
        """
        Show/hide docstring window.
        """
        settings.show_docstring = not settings.show_docstring

    @handle(Keys.F10)
    def _(event):
        """
        Show/hide line numbers
        """
        settings.show_line_numbers = not settings.show_line_numbers

    @handle(Keys.Tab, filter= ~has_selection & TabShouldInsertWhitespaceFilter())
    def _(event):
        """
        When tab should insert whitespace, do that instead of completion.
        """
        event.cli.current_buffer.insert_text('    ')

    @handle(Keys.ControlJ, filter= ~has_selection &
            ~(ViModeEnabled(key_bindings_manager) &
              ViStateFilter(key_bindings_manager.vi_state, InputMode.NAVIGATION)) &
            HasFocus('default') & IsMultiline())
    def _(event):
        """
        Behaviour of the Enter key.

        Auto indent after newline/Enter.
        (When not in Vi navigaton mode, and when multiline is enabled.)
        """
        b = event.current_buffer

        def at_the_end(b):
            """ we consider the cursor at the end when there is no text after
            the cursor, or only whitespace. """
            text = b.document.text_after_cursor
            return text == '' or (text.isspace() and not '\n' in text)

        if settings.paste_mode:
            # In paste mode, always insert text.
            b.insert_text('\n')

        elif at_the_end(b) and b.document.text.replace(' ', '').endswith('\n'):
            if b.validate():
                # When the cursor is at the end, and we have an empty line:
                # drop the empty lines, but return the value.
                b.document = Document(
                    text=b.text.rstrip(),
                    cursor_position=len(b.text.rstrip()))

                b.append_to_history()
                event.cli.set_return_value(b.document)
        else:
            auto_newline(b)


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

        # Copy whitespace from current line
        for c in current_line:
            if c.isspace():
                insert_text(c)
            else:
                break

        # If the last line ends with a colon, add four extra spaces.
        if current_line[-1:] == ':':
            for x in range(4):
                insert_text(' ')

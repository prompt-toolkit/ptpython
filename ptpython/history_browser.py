"""
Utility to easily select lines from the history and execute them again.

`create_history_application` creates an `Application` instance that runs will
run as a sub application of the Repl/PythonInput.
"""
from __future__ import unicode_literals

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer, AcceptAction
from prompt_toolkit.buffer_mapping import BufferMapping
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition, HasFocus, InFocusStack
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float, ConditionalContainer, Container, ScrollOffsets
from prompt_toolkit.layout.controls import BufferControl, FillControl
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.layout.margins import Margin, ScrollbarMargin
from prompt_toolkit.layout.processors import Processor, Transformation, HighlightSearchProcessor, HighlightSelectionProcessor
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.layout.toolbars import ArgToolbar, SearchToolbar
from prompt_toolkit.layout.toolbars import TokenListToolbar
from prompt_toolkit.layout.utils import token_list_to_text
from pygments.lexers import RstLexer
from pygments.token import Token

from .utils import if_mousedown

from ptpython.layout import get_inputmode_tokens
from functools import partial
import six

if six.PY2:
    from pygments.lexers import PythonLexer
else:
    from pygments.lexers import Python3Lexer as PythonLexer


HISTORY_BUFFER = 'HISTORY_BUFFER'
HELP_BUFFER = 'HELP_BUFFER'

HISTORY_COUNT = 2000

__all__ = (
    'create_history_application',
)

HELP_TEXT = """
This interface is meant to select multiple lines from the
history and execute them together.

Typical usage
-------------

1. Move the ``cursor up`` in the history pane, until the
   cursor is on the first desired line.
2. Hold down the ``space bar``, or press it multiple
   times. Each time it will select one line and move to
   the next one. Each selected line will appear on the
   right side.
3. When all the required lines are displayed on the right
   side, press ``Enter``. This will go back to the Python
   REPL and show these lines as the current input. They
   can still be edited from there.

Key bindings
------------

Many Emacs and Vi navigation key bindings should work.
Press ``F4`` to switch between Emacs and Vi mode.

Additional bindings:

- ``Space``: Select or delect a line.
- ``Tab``: Move the focus between the history and input
  pane. (Alternative: ``Ctrl-W``)
- ``Ctrl-C``: Cancel. Ignore the result and go back to
  the REPL. (Alternatives: ``q`` and ``Control-G``.)
- ``Enter``: Accept the result and go back to the REPL.
- ``F1``: Show/hide help. Press ``Enter`` to quit this
  help message.

Further, remember that searching works like in Emacs
(using ``Ctrl-R``) or Vi (using ``/``).
"""


class BORDER:
    " Box drawing characters. "
    HORIZONTAL = '\u2501'
    VERTICAL = '\u2503'
    TOP_LEFT = '\u250f'
    TOP_RIGHT = '\u2513'
    BOTTOM_LEFT = '\u2517'
    BOTTOM_RIGHT = '\u251b'
    LIGHT_VERTICAL = '\u2502'


def create_popup_window(title, body):
    """
    Return the layout for a pop-up window. It consists of a title bar showing
    the `title` text, and a body layout. The window is surrounded by borders.
    """
    assert isinstance(title, six.text_type)
    assert isinstance(body, Container)

    return HSplit([
        VSplit([
            Window(width=D.exact(1), height=D.exact(1),
                   content=FillControl(BORDER.TOP_LEFT, token=Token.Window.Border)),
            TokenListToolbar(
                get_tokens=lambda cli: [(Token.Window.Title, ' %s ' % title)],
                align_center=True,
                default_char=Char(BORDER.HORIZONTAL, Token.Window.Border)),
            Window(width=D.exact(1), height=D.exact(1),
                   content=FillControl(BORDER.TOP_RIGHT, token=Token.Window.Border)),
        ]),
        VSplit([
            Window(width=D.exact(1),
                   content=FillControl(BORDER.VERTICAL, token=Token.Window.Border)),
            body,
            Window(width=D.exact(1),
                   content=FillControl(BORDER.VERTICAL, token=Token.Window.Border)),
        ]),
        VSplit([
            Window(width=D.exact(1), height=D.exact(1),
                   content=FillControl(BORDER.BOTTOM_LEFT, token=Token.Window.Border)),
            Window(height=D.exact(1),
                   content=FillControl(BORDER.HORIZONTAL, token=Token.Window.Border)),
            Window(width=D.exact(1), height=D.exact(1),
                   content=FillControl(BORDER.BOTTOM_RIGHT, token=Token.Window.Border)),
        ]),
    ])


def create_layout(python_input, history_mapping):
    """
    Create and return a `Container` instance for the history
    application.
    """
    processors = [
        HighlightSearchProcessor(preview_search=True),
        HighlightSelectionProcessor()]

    help_window = create_popup_window(
        title='History Help',
        body=Window(
            content=BufferControl(
                buffer_name=HELP_BUFFER,
                default_char=Char(token=Token),
                lexer=PygmentsLexer(RstLexer),
                input_processors=processors),
            right_margins=[ScrollbarMargin()],
            scroll_offsets=ScrollOffsets(top=2, bottom=2)))

    return HSplit([
        #  Top title bar.
        TokenListToolbar(
            get_tokens=_get_top_toolbar_tokens,
            align_center=True,
            default_char=Char(' ', Token.Toolbar.Status)),
        FloatContainer(
            content=VSplit([
                # Left side: history.
                Window(
                    content=BufferControl(
                        buffer_name=HISTORY_BUFFER,
                        lexer=PygmentsLexer(PythonLexer),
                        input_processors=processors),
                    wrap_lines=False,
                    left_margins=[HistoryMargin(history_mapping)],
                    scroll_offsets=ScrollOffsets(top=2, bottom=2)),
                # Separator.
                Window(width=D.exact(1),
                       content=FillControl(BORDER.LIGHT_VERTICAL, token=Token.Separator)),
                # Right side: result.
                Window(
                    content=BufferControl(
                        buffer_name=DEFAULT_BUFFER,
                        input_processors=processors + [GrayExistingText(history_mapping)],
                        lexer=PygmentsLexer(PythonLexer)),
                    wrap_lines=False,
                    left_margins=[ResultMargin(history_mapping)],
                    scroll_offsets=ScrollOffsets(top=2, bottom=2)),
            ]),
            floats=[
                # Help text as a float.
                Float(width=60, top=3, bottom=2,
                      content=ConditionalContainer(
                          # (We use InFocusStack, because it's possible to search
                          # through the help text as well, and at that point the search
                          # buffer has the focus.)
                          content=help_window, filter=InFocusStack(HELP_BUFFER))),
            ]
        ),
        # Bottom toolbars.
        ArgToolbar(),
        SearchToolbar(),
        TokenListToolbar(
            get_tokens=partial(_get_bottom_toolbar_tokens, python_input=python_input),
            default_char=Char(' ', Token.Toolbar.Status)),
    ])


def _get_top_toolbar_tokens(cli):
    return [(Token.Toolbar.Status.Title, 'History browser - Insert from history')]


def _get_bottom_toolbar_tokens(cli, python_input):
    @if_mousedown
    def f1(cli, mouse_event):
        _toggle_help(cli)

    @if_mousedown
    def tab(cli, mouse_event):
        _select_other_window(cli)

    return [
        (Token.Toolbar.Status, ' ')
    ] + get_inputmode_tokens(cli, python_input) + [
        (Token.Toolbar.Status, ' '),
        (Token.Toolbar.Status.Key, '[Space]'),
        (Token.Toolbar.Status, ' Toggle '),
        (Token.Toolbar.Status.Key, '[Tab]', tab),
        (Token.Toolbar.Status, ' Focus ', tab),
        (Token.Toolbar.Status.Key, '[Enter]'),
        (Token.Toolbar.Status, ' Accept '),
        (Token.Toolbar.Status.Key, '[F1]', f1),
        (Token.Toolbar.Status, ' Help ', f1),
    ]


class HistoryMargin(Margin):
    """
    Margin for the history buffer.
    This displays a green bar for the selected entries.
    """
    def __init__(self, history_mapping):
        self.history_mapping = history_mapping

    def get_width(self, cli, ui_content):
        return 2

    def create_margin(self, cli, window_render_info, width, height):
        document = cli.buffers[HISTORY_BUFFER].document

        lines_starting_new_entries = self.history_mapping.lines_starting_new_entries
        selected_lines = self.history_mapping.selected_lines

        current_lineno = document.cursor_position_row

        visible_line_to_input_line = window_render_info.visible_line_to_input_line
        result = []

        for y in range(height):
            line_number = visible_line_to_input_line.get(y)

            # Show stars at the start of each entry.
            # (Visualises multiline entries.)
            if line_number in lines_starting_new_entries:
                char = '*'
            else:
                char = ' '

            if line_number in selected_lines:
                t = Token.History.Line.Selected
            else:
                t = Token.History.Line

            if line_number == current_lineno:
                t = t.Current

            result.append((t, char))
            result.append((Token, '\n'))

        return result


class ResultMargin(Margin):
    """
    The margin to be shown in the result pane.
    """
    def __init__(self, history_mapping):
        self.history_mapping = history_mapping

    def get_width(self, cli, ui_content):
        return 2

    def create_margin(self, cli, window_render_info, width, height):
        document = cli.buffers[DEFAULT_BUFFER].document

        current_lineno = document.cursor_position_row
        offset = self.history_mapping.result_line_offset #original_document.cursor_position_row

        visible_line_to_input_line = window_render_info.visible_line_to_input_line

        result = []

        for y in range(height):
            line_number = visible_line_to_input_line.get(y)

            if (line_number is None or line_number < offset or
                    line_number >= offset + len(self.history_mapping.selected_lines)):
                t = Token
            elif line_number == current_lineno:
                t = Token.History.Line.Selected.Current
            else:
                t = Token.History.Line.Selected

            result.append((t, ' '))
            result.append((Token, '\n'))

        return result

    def invalidation_hash(self, cli, document):
        return document.cursor_position_row


class GrayExistingText(Processor):
    """
    Turn the existing input, before and after the inserted code gray.
    """
    def __init__(self, history_mapping):
        self.history_mapping = history_mapping
        self._lines_before = len(history_mapping.original_document.text_before_cursor.splitlines())

    def apply_transformation(self, cli, document, lineno, source_to_display, tokens):
        if (lineno < self._lines_before or
                lineno >= self._lines_before + len(self.history_mapping.selected_lines)):
            text = token_list_to_text(tokens)
            return Transformation(tokens=[(Token.History.ExistingInput, text)])
        else:
            return Transformation(tokens=tokens)


class HistoryMapping(object):
    """
    Keep a list of all the lines from the history and the selected lines.
    """
    def __init__(self, python_history, original_document):
        self.python_history = python_history
        self.original_document = original_document

        self.lines_starting_new_entries = set()
        self.selected_lines = set()

        # Process history.
        history_lines = []

        for entry_nr, entry in list(enumerate(python_history))[-HISTORY_COUNT:]:
            self.lines_starting_new_entries.add(len(history_lines))

            for line in entry.splitlines():
                history_lines.append(line)

        if len(python_history) > HISTORY_COUNT:
            history_lines[0] = '# *** History has been truncated to %s lines ***' % HISTORY_COUNT

        self.history_lines = history_lines
        self.concatenated_history = '\n'.join(history_lines)

        # Line offset.
        if self.original_document.text_before_cursor:
            self.result_line_offset = self.original_document.cursor_position_row + 1
        else:
            self.result_line_offset = 0

    def get_new_document(self, cursor_pos=None):
        """
        Create a `Document` instance that contains the resulting text.
        """
        lines = []

        # Original text, before cursor.
        if self.original_document.text_before_cursor:
            lines.append(self.original_document.text_before_cursor)

        # Selected entries from the history.
        for line_no in sorted(self.selected_lines):
            lines.append(self.history_lines[line_no])

        # Original text, after cursor.
        if self.original_document.text_after_cursor:
            lines.append(self.original_document.text_after_cursor)

        # Create `Document` with cursor at the right position.
        text = '\n'.join(lines)
        if cursor_pos is not None and cursor_pos > len(text):
            cursor_pos = len(text)
        return Document(text, cursor_pos)

    def update_default_buffer(self, cli):
        b = cli.buffers[DEFAULT_BUFFER]

        b.set_document(
            self.get_new_document(b.cursor_position), bypass_readonly=True)


def _toggle_help(cli):
    " Display/hide help. "
    if cli.current_buffer_name == HELP_BUFFER:
        cli.pop_focus()
    else:
        cli.push_focus(HELP_BUFFER)


def _select_other_window(cli):
    " Toggle focus between left/right window. "
    if cli.current_buffer_name == HISTORY_BUFFER:
        cli.focus(DEFAULT_BUFFER)

    elif cli.current_buffer_name == DEFAULT_BUFFER:
        cli.focus(HISTORY_BUFFER)


def create_key_bindings(python_input, history_mapping):
    """
    Key bindings.
    """
    manager = KeyBindingManager(
        enable_search=True,
        enable_extra_page_navigation=True)
    handle = manager.registry.add_binding

    @handle(' ', filter=HasFocus(HISTORY_BUFFER))
    def _(event):
        """
        Space: select/deselect line from history pane.
        """
        b = event.current_buffer
        line_no = b.document.cursor_position_row

        if line_no in history_mapping.selected_lines:
            # Remove line.
            history_mapping.selected_lines.remove(line_no)
            history_mapping.update_default_buffer(event.cli)
        else:
            # Add line.
            history_mapping.selected_lines.add(line_no)
            history_mapping.update_default_buffer(event.cli)

            # Update cursor position
            default_buffer = event.cli.buffers[DEFAULT_BUFFER]
            default_lineno = sorted(history_mapping.selected_lines).index(line_no) + \
                history_mapping.result_line_offset
            default_buffer.cursor_position = \
                default_buffer.document.translate_row_col_to_index(default_lineno, 0)

        # Also move the cursor to the next line. (This way they can hold
        # space to select a region.)
        b.cursor_position = b.document.translate_row_col_to_index(line_no + 1, 0)

    @handle(' ', filter=HasFocus(DEFAULT_BUFFER))
    @handle(Keys.Delete, filter=HasFocus(DEFAULT_BUFFER))
    @handle(Keys.ControlH, filter=HasFocus(DEFAULT_BUFFER))
    def _(event):
        """
        Space: remove line from default pane.
        """
        b = event.current_buffer
        line_no = b.document.cursor_position_row - history_mapping.result_line_offset

        if line_no >= 0:
            try:
                history_lineno = sorted(history_mapping.selected_lines)[line_no]
            except IndexError:
                pass  # When `selected_lines` is an empty set.
            else:
                history_mapping.selected_lines.remove(history_lineno)

            history_mapping.update_default_buffer(event.cli)

    help_focussed = HasFocus(HELP_BUFFER)
    main_buffer_focussed = HasFocus(HISTORY_BUFFER) | HasFocus(DEFAULT_BUFFER)

    @handle(Keys.Tab, filter=main_buffer_focussed)
    @handle(Keys.ControlX, filter=main_buffer_focussed, eager=True)
        # Eager: ignore the Emacs [Ctrl-X Ctrl-X] binding.
    @handle(Keys.ControlW, filter=main_buffer_focussed)
    def _(event):
        " Select other window. "
        _select_other_window(event.cli)

    @handle(Keys.F4)
    def _(event):
        " Switch between Emacs/Vi mode. "
        python_input.vi_mode = not python_input.vi_mode

    @handle(Keys.F1)
    def _(event):
        " Display/hide help. "
        _toggle_help(event.cli)

    @handle(Keys.ControlJ, filter=help_focussed)
    @handle(Keys.ControlC, filter=help_focussed)
    @handle(Keys.ControlG, filter=help_focussed)
    @handle(Keys.Escape, filter=help_focussed)
    def _(event):
        " Leave help. "
        event.cli.pop_focus()

    @handle('q', filter=main_buffer_focussed)
    @handle(Keys.F3, filter=main_buffer_focussed)
    @handle(Keys.ControlC, filter=main_buffer_focussed)
    @handle(Keys.ControlG, filter=main_buffer_focussed)
    def _(event):
        " Cancel and go back. "
        event.cli.set_return_value(None)

    enable_system_bindings = Condition(lambda cli: python_input.enable_system_bindings)

    @handle(Keys.ControlZ, filter=enable_system_bindings)
    def _(event):
        " Suspend to background. "
        event.cli.suspend_to_background()

    return manager.registry


def create_history_application(python_input, original_document):
    """
    Create an `Application` for the history screen.
    This has to be run as a sub application of `python_input`.

    When this application runs and returns, it retuns the selected lines.
    """
    history_mapping = HistoryMapping(python_input.history, original_document)

    def default_buffer_pos_changed(_):
        """ When the cursor changes in the default buffer. Synchronize with
        history buffer. """
        # Only when this buffer has the focus.
        if buffer_mapping.focus_stack[-1] == DEFAULT_BUFFER:
            try:
                line_no = default_buffer.document.cursor_position_row - \
                    history_mapping.result_line_offset

                if line_no < 0:  # When the cursor is above the inserted region.
                    raise IndexError

                history_lineno = sorted(history_mapping.selected_lines)[line_no]
            except IndexError:
                pass
            else:
                history_buffer.cursor_position = \
                    history_buffer.document.translate_row_col_to_index(history_lineno, 0)

    def history_buffer_pos_changed(_):
        """ When the cursor changes in the history buffer. Synchronize. """
        # Only when this buffer has the focus.
        if buffer_mapping.focus_stack[-1] == HISTORY_BUFFER:
            line_no = history_buffer.document.cursor_position_row

            if line_no in history_mapping.selected_lines:
                default_lineno = sorted(history_mapping.selected_lines).index(line_no) + \
                    history_mapping.result_line_offset

                default_buffer.cursor_position = \
                    default_buffer.document.translate_row_col_to_index(default_lineno, 0)

    history_buffer = Buffer(
        initial_document=Document(history_mapping.concatenated_history),
        on_cursor_position_changed=history_buffer_pos_changed,
        accept_action=AcceptAction(
            lambda cli, buffer: cli.set_return_value(default_buffer.document)),
        read_only=True)

    default_buffer = Buffer(
        initial_document=history_mapping.get_new_document(),
        on_cursor_position_changed=default_buffer_pos_changed,
        read_only=True)

    help_buffer = Buffer(
        initial_document=Document(HELP_TEXT, 0),
        accept_action=AcceptAction.IGNORE,
        read_only=True
    )

    buffer_mapping = BufferMapping({
        HISTORY_BUFFER: history_buffer,
        DEFAULT_BUFFER: default_buffer,
        HELP_BUFFER: help_buffer,
    }, initial=HISTORY_BUFFER)

    application = Application(
        layout=create_layout(python_input, history_mapping),
        use_alternate_screen=True,
        buffers=buffer_mapping,
        style=python_input._current_style,
        mouse_support=Condition(lambda cli: python_input.enable_mouse_support),
        key_bindings_registry=create_key_bindings(python_input, history_mapping)
    )
    return application

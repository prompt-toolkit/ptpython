"""
Utility to easily select lines from the history and execute them again.

`create_history_application` creates an `Application` instance that runs will
run as a sub application of the Repl/PythonInput.
"""
from __future__ import unicode_literals

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.key_binding.defaults import load_key_bindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float, ConditionalContainer, Container, ScrollOffsets, Align
from prompt_toolkit.layout.controls import BufferControl, TokenListControl
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.layout.margins import Margin, ScrollbarMargin
from prompt_toolkit.layout.processors import Processor, Transformation, HighlightSearchProcessor, HighlightSelectionProcessor, merge_processors
from prompt_toolkit.layout.toolbars import ArgToolbar, SearchToolbar
from prompt_toolkit.layout.utils import token_list_to_text
from prompt_toolkit.token import Token
from pygments.lexers import RstLexer

from .utils import if_mousedown

from ptpython.layout import get_inputmode_tokens
from functools import partial
import six

if six.PY2:
    from pygments.lexers import PythonLexer
else:
    from pygments.lexers import Python3Lexer as PythonLexer


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
                   char=BORDER.TOP_LEFT,
                   token=Token.Window.Border),
            Window(
                content=TokenListControl(
                    get_tokens=lambda app: [(Token.Window.Title, ' %s ' % title)]),
                align=Align.CENTER,
                char=BORDER.HORIZONTAL,
                token=Token.Window.Border),
            Window(width=D.exact(1), height=D.exact(1),
                   char=BORDER.TOP_RIGHT,
                   token=Token.Window.Border),
        ]),
        VSplit([
            Window(width=D.exact(1),
                   char=BORDER.VERTICAL,
                   token=Token.Window.Border),
            body,
            Window(width=D.exact(1),
                   char=BORDER.VERTICAL,
                   token=Token.Window.Border),
        ]),
        VSplit([
            Window(width=D.exact(1), height=D.exact(1),
                   char=BORDER.BOTTOM_LEFT,
                   token=Token.Window.Border),
            Window(height=D.exact(1),
                   char=BORDER.HORIZONTAL,
                   token=Token.Window.Border),
            Window(width=D.exact(1), height=D.exact(1),
                   char=BORDER.BOTTOM_RIGHT,
                   token=Token.Window.Border),
        ]),
    ])


class HistoryLayout(object):
    """
    Create and return a `Container` instance for the history
    application.
    """
    def __init__(self, history):
        default_processors = [
            HighlightSearchProcessor(preview_search=True),
            HighlightSelectionProcessor()
        ]

        self.help_buffer_control = BufferControl(
            buffer=history.help_buffer,
            lexer=PygmentsLexer(RstLexer),
            input_processor=merge_processors(default_processors))

        help_window = create_popup_window(
            title='History Help',
            body=Window(
                content=self.help_buffer_control,
                right_margins=[ScrollbarMargin()],
                scroll_offsets=ScrollOffsets(top=2, bottom=2),
                transparent=False))

        self.default_buffer_control = BufferControl(
            buffer=history.default_buffer,
            input_processor=merge_processors(
                default_processors + [GrayExistingText(history.history_mapping)]),
            lexer=PygmentsLexer(PythonLexer))

        self.history_buffer_control = BufferControl(
            buffer=history.history_buffer,
            lexer=PygmentsLexer(PythonLexer),
            input_processor=merge_processors(default_processors))

        history_window = Window(
            content=self.history_buffer_control,
            wrap_lines=False,
            left_margins=[HistoryMargin(history)],
            scroll_offsets=ScrollOffsets(top=2, bottom=2))

        self.root_container = HSplit([
            #  Top title bar.
            Window(
                content=TokenListControl(get_tokens=_get_top_toolbar_tokens),
                align=Align.CENTER,
                token=Token.Toolbar.Status),
            FloatContainer(
                content=VSplit([
                    # Left side: history.
                    history_window,
                    # Separator.
                    Window(width=D.exact(1),
                           char=BORDER.LIGHT_VERTICAL,
                           token=Token.Separator),
                    # Right side: result.
                    Window(
                        content=self.default_buffer_control,
                        wrap_lines=False,
                        left_margins=[ResultMargin(history)],
                        scroll_offsets=ScrollOffsets(top=2, bottom=2)),
                ]),
                floats=[
                    # Help text as a float.
                    Float(width=60, top=3, bottom=2,
                          content=ConditionalContainer(
                                    # XXXX XXX
                              # (We use InFocusStack, because it's possible to search
                              # through the help text as well, and at that point the search
                              # buffer has the focus.)
                              content=help_window, filter=has_focus(history.help_buffer))),  # XXX
                ]
            ),
            # Bottom toolbars.
            ArgToolbar(),
    #        SearchToolbar(),  # XXX
            Window(
                content=TokenListControl(
                    get_tokens=partial(_get_bottom_toolbar_tokens, history=history)),
                token=Token.Toolbar.Status),
        ])

        self.layout = Layout(self.root_container, history_window)


def _get_top_toolbar_tokens(app):
    return [(Token.Toolbar.Status.Title, 'History browser - Insert from history')]


def _get_bottom_toolbar_tokens(app, history):
    python_input = history.python_input
    @if_mousedown
    def f1(app, mouse_event):
        _toggle_help(history)

    @if_mousedown
    def tab(app, mouse_event):
        _select_other_window(history)

    return [
        (Token.Toolbar.Status, ' ')
    ] + get_inputmode_tokens(app, python_input) + [
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
    def __init__(self, history):
        self.history_buffer = history.history_buffer
        self.history_mapping = history.history_mapping

    def get_width(self, app, ui_content):
        return 2

    def create_margin(self, app, window_render_info, width, height):
        document = self.history_buffer.document

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
    def __init__(self, history):
        self.history_mapping = history.history_mapping
        self.history_buffer = history.history_buffer

    def get_width(self, app, ui_content):
        return 2

    def create_margin(self, app, window_render_info, width, height):
        document = self.history_buffer.document

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

    def invalidation_hash(self, app, document):
        return document.cursor_position_row


class GrayExistingText(Processor):
    """
    Turn the existing input, before and after the inserted code gray.
    """
    def __init__(self, history_mapping):
        self.history_mapping = history_mapping
        self._lines_before = len(history_mapping.original_document.text_before_cursor.splitlines())

    def apply_transformation(self, transformation_input):
        app = transformation_input.app
        lineno = transformation_input.lineno
        tokens = transformation_input.tokens

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
    def __init__(self, history, python_history, original_document):
        self.history = history
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

    def update_default_buffer(self, app):
        b = self.history.default_buffer

        b.set_document(
            self.get_new_document(b.cursor_position), bypass_readonly=True)


def _toggle_help(history):
    " Display/hide help. "
    help_buffer_control = history.history_layout.help_buffer_control

    if history.app.layout.current_control == help_buffer_control:
        history.app.layout.pop_focus()
    else:
        history.app.layout.current_control = help_buffer_control


def _select_other_window(history):
    " Toggle focus between left/right window. "
    current_buffer = history.app.current_buffer
    layout = history.history_layout.layout

    if current_buffer == history.history_buffer:
        layout.current_control = history.history_layout.default_buffer_control

    elif current_buffer == history.default_buffer:
        layout.current_control = history.history_layout.history_buffer_control


def create_key_bindings(history, python_input, history_mapping):
    """
    Key bindings.
    """
    bindings = KeyBindings()
    handle = bindings.add

    @handle(' ', filter=has_focus(history.history_buffer))
    def _(event):
        """
        Space: select/deselect line from history pane.
        """
        b = event.current_buffer
        line_no = b.document.cursor_position_row

        if line_no in history_mapping.selected_lines:
            # Remove line.
            history_mapping.selected_lines.remove(line_no)
            history_mapping.update_default_buffer(event.app)
        else:
            # Add line.
            history_mapping.selected_lines.add(line_no)
            history_mapping.update_default_buffer(event.app)

            # Update cursor position
            default_buffer = history.default_buffer
            default_lineno = sorted(history_mapping.selected_lines).index(line_no) + \
                history_mapping.result_line_offset
            default_buffer.cursor_position = \
                default_buffer.document.translate_row_col_to_index(default_lineno, 0)

        # Also move the cursor to the next line. (This way they can hold
        # space to select a region.)
        b.cursor_position = b.document.translate_row_col_to_index(line_no + 1, 0)

    @handle(' ', filter=has_focus(DEFAULT_BUFFER))
    @handle(Keys.Delete, filter=has_focus(DEFAULT_BUFFER))
    @handle(Keys.ControlH, filter=has_focus(DEFAULT_BUFFER))
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

            history_mapping.update_default_buffer(event.app)

    help_focussed = has_focus(history.help_buffer)
    main_buffer_focussed = has_focus(history.history_buffer) | has_focus(history.default_buffer)

    @handle(Keys.Tab, filter=main_buffer_focussed)
    @handle(Keys.ControlX, filter=main_buffer_focussed, eager=True)
        # Eager: ignore the Emacs [Ctrl-X Ctrl-X] binding.
    @handle(Keys.ControlW, filter=main_buffer_focussed)
    def _(event):
        " Select other window. "
        _select_other_window(history)

    @handle(Keys.F4)
    def _(event):
        " Switch between Emacs/Vi mode. "
        python_input.vi_mode = not python_input.vi_mode

    @handle(Keys.F1)
    def _(event):
        " Display/hide help. "
        _toggle_help(history)

    @handle(Keys.Enter, filter=help_focussed)
    @handle(Keys.ControlC, filter=help_focussed)
    @handle(Keys.ControlG, filter=help_focussed)
    @handle(Keys.Escape, filter=help_focussed)
    def _(event):
        " Leave help. "
        event.app.layout.pop_focus()

    @handle('q', filter=main_buffer_focussed)
    @handle(Keys.F3, filter=main_buffer_focussed)
    @handle(Keys.ControlC, filter=main_buffer_focussed)
    @handle(Keys.ControlG, filter=main_buffer_focussed)
    def _(event):
        " Cancel and go back. "
        event.app.set_return_value(None)

    @handle(Keys.Enter, filter=main_buffer_focussed)
    def _(event):
        " Accept input. "
        event.app.set_return_value(history.default_buffer.document)

    enable_system_bindings = Condition(lambda app: python_input.enable_system_bindings)

    @handle(Keys.ControlZ, filter=enable_system_bindings)
    def _(event):
        " Suspend to background. "
        event.app.suspend_to_background()

    return merge_key_bindings([
        load_key_bindings(
            enable_search=True,
            enable_extra_page_navigation=True),
        bindings
    ])


class History(object):
    def __init__(self, python_input, original_document):
        """
        Create an `Application` for the history screen.
        This has to be run as a sub application of `python_input`.

        When this application runs and returns, it retuns the selected lines.
        """
        self.python_input = python_input

        history_mapping = HistoryMapping(self, python_input.history, original_document)
        self.history_mapping = history_mapping

        self.history_buffer = Buffer(
            loop=python_input.loop,
            document=Document(history_mapping.concatenated_history),
            on_cursor_position_changed=self._history_buffer_pos_changed,
            accept_handler=(
                lambda app, buffer: app.set_return_value(self.default_buffer.text)),
            read_only=True)

        self.default_buffer = Buffer(
            loop=python_input.loop,
            name=DEFAULT_BUFFER,
            document=history_mapping.get_new_document(),
            on_cursor_position_changed=self._default_buffer_pos_changed,
            read_only=True)

        self.help_buffer = Buffer(
            loop=python_input.loop,
            document=Document(HELP_TEXT, 0),
            read_only=True
        )

        self.history_layout = HistoryLayout(self)

        self.app = Application(
            loop=python_input.loop,
            layout=self.history_layout.layout,
            use_alternate_screen=True,
            style=python_input._current_style,
            mouse_support=Condition(lambda app: python_input.enable_mouse_support),
            key_bindings=create_key_bindings(self, python_input, history_mapping)
        )

    def _default_buffer_pos_changed(self, _):
        """ When the cursor changes in the default buffer. Synchronize with
        history buffer. """
        # Only when this buffer has the focus.
        if self.app.current_buffer == self.default_buffer:
            try:
                line_no = self.default_buffer.document.cursor_position_row - \
                    self.history_mapping.result_line_offset

                if line_no < 0:  # When the cursor is above the inserted region.
                    raise IndexError

                history_lineno = sorted(self.history_mapping.selected_lines)[line_no]
            except IndexError:
                pass
            else:
                self.history_buffer.cursor_position = \
                    self.history_buffer.document.translate_row_col_to_index(history_lineno, 0)

    def _history_buffer_pos_changed(self, _):
        """ When the cursor changes in the history buffer. Synchronize. """
        # Only when this buffer has the focus.
        if self.app.current_buffer == self.history_buffer:
            line_no = self.history_buffer.document.cursor_position_row

            if line_no in self.history_mapping.selected_lines:
                default_lineno = sorted(self.history_mapping.selected_lines).index(line_no) + \
                    self.history_mapping.result_line_offset

                self.default_buffer.cursor_position = \
                    self.default_buffer.document.translate_row_col_to_index(default_lineno, 0)


"""
Creation of the `Layout` instance for the Python input/REPL.
"""
from __future__ import unicode_literals

from prompt_toolkit.application import get_app
from prompt_toolkit.enums import DEFAULT_BUFFER, SEARCH_BUFFER
from prompt_toolkit.filters import is_done, has_completions, renderer_height_is_known, has_focus, Condition
from prompt_toolkit.formatted_text import fragment_list_width, to_formatted_text
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.layout.containers import Window, HSplit, VSplit, FloatContainer, Float, ConditionalContainer, ScrollOffsets
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.margins import PromptMargin
from prompt_toolkit.layout.menus import CompletionsMenu, MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import ConditionalProcessor, AppendAutoSuggestion, HighlightIncrementalSearchProcessor, HighlightSelectionProcessor, HighlightMatchingBracketProcessor, Processor, Transformation
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.selection import SelectionType
from prompt_toolkit.widgets.toolbars import CompletionsToolbar, ArgToolbar, SearchToolbar, ValidationToolbar, SystemToolbar

from .filters import HasSignature, ShowSidebar, ShowSignature, ShowDocstring
from .utils import if_mousedown

from pygments.lexers import PythonLexer

import platform
import sys

__all__ = (
    'PtPythonLayout',
    'CompletionVisualisation',
)


# DisplayMultipleCursors: Only for prompt_toolkit>=1.0.8
try:
    from prompt_toolkit.layout.processors import DisplayMultipleCursors
except ImportError:
    class DisplayMultipleCursors(Processor):
        " Dummy. "
        def __init__(self, *a):
            pass

        def apply_transformation(self, document, lineno,
                                 source_to_display, tokens):
            return Transformation(tokens)


class CompletionVisualisation:
    " Visualisation method for the completions. "
    NONE = 'none'
    POP_UP = 'pop-up'
    MULTI_COLUMN = 'multi-column'
    TOOLBAR = 'toolbar'


def show_completions_toolbar(python_input):
    return Condition(lambda: python_input.completion_visualisation == CompletionVisualisation.TOOLBAR)


def show_completions_menu(python_input):
    return Condition(lambda: python_input.completion_visualisation == CompletionVisualisation.POP_UP)


def show_multi_column_completions_menu(python_input):
    return Condition(lambda: python_input.completion_visualisation == CompletionVisualisation.MULTI_COLUMN)


def python_sidebar(python_input):
    """
    Create the `Layout` for the sidebar with the configurable options.
    """
    def get_text_fragments():
        tokens = []

        def append_category(category):
            tokens.extend([
                ('class:sidebar', '  '),
                ('class:sidebar.title', '   %-36s' % category.title),
                ('class:sidebar', '\n'),
            ])

        def append(index, label, status):
            selected = index == python_input.selected_option_index

            @if_mousedown
            def select_item(mouse_event):
                python_input.selected_option_index = index

            @if_mousedown
            def goto_next(mouse_event):
                " Select item and go to next value. "
                python_input.selected_option_index = index
                option = python_input.selected_option
                option.activate_next()

            sel = ',selected' if selected else ''

            tokens.append(('class:sidebar' + sel, ' >' if selected else '  '))
            tokens.append(('class:sidebar.label' + sel, '%-24s' % label, select_item))
            tokens.append(('class:sidebar.status' + sel, ' ', select_item))
            tokens.append(('class:sidebar.status' + sel, '%s' % status, goto_next))

            if selected:
                tokens.append(('[SetCursorPosition]', ''))

            tokens.append(('class:sidebar.status' + sel, ' ' * (13 - len(status)), goto_next))
            tokens.append(('class:sidebar', '<' if selected else ''))
            tokens.append(('class:sidebar', '\n'))

        i = 0
        for category in python_input.options:
            append_category(category)

            for option in category.options:
                append(i, option.title, '%s' % option.get_current_value())
                i += 1

        tokens.pop()  # Remove last newline.

        return tokens

    class Control(FormattedTextControl):
        def move_cursor_down(self):
            python_input.selected_option_index += 1

        def move_cursor_up(self):
            python_input.selected_option_index -= 1

    return Window(
        Control(get_text_fragments),
        style='class:sidebar',
        width=Dimension.exact(43),
        height=Dimension(min=3),
        scroll_offsets=ScrollOffsets(top=1, bottom=1))


def python_sidebar_navigation(python_input):
    """
    Create the `Layout` showing the navigation information for the sidebar.
    """
    def get_text_fragments():
        tokens = []

        # Show navigation info.
        tokens.extend([
            ('class:sidebar', '    '),
            ('class:sidebar.key', '[Arrows]'),
            ('class:sidebar', ' '),
            ('class:sidebar.description', 'Navigate'),
            ('class:sidebar', ' '),
            ('class:sidebar.key', '[Enter]'),
            ('class:sidebar', ' '),
            ('class:sidebar.description', 'Hide menu'),
        ])

        return tokens

    return Window(
        FormattedTextControl(get_text_fragments),
        style='class:sidebar',
        width=Dimension.exact(43),
        height=Dimension.exact(1))


def python_sidebar_help(python_input):
    """
    Create the `Layout` for the help text for the current item in the sidebar.
    """
    token = 'class:sidebar.helptext'

    def get_current_description():
        """
        Return the description of the selected option.
        """
        i = 0
        for category in python_input.options:
            for option in category.options:
                if i == python_input.selected_option_index:
                    return option.description
                i += 1
        return ''

    def get_help_text():
        return [(token, get_current_description())]

    return ConditionalContainer(
        content=Window(
            FormattedTextControl(get_help_text),
            style=token,
            height=Dimension(min=3)),
        filter=ShowSidebar(python_input) &
               Condition(lambda: python_input.show_sidebar_help) & ~is_done)


def signature_toolbar(python_input):
    """
    Return the `Layout` for the signature.
    """
    def get_text_fragments():
        result = []
        append = result.append
        Signature = 'class:signature-toolbar'

        if python_input.signatures:
            sig = python_input.signatures[0]  # Always take the first one.

            append((Signature, ' '))
            try:
                append((Signature, sig.full_name))
            except IndexError:
                # Workaround for #37: https://github.com/jonathanslenders/python-prompt-toolkit/issues/37
                # See also: https://github.com/davidhalter/jedi/issues/490
                return []

            append((Signature + ',operator', '('))

            try:
                enumerated_params = enumerate(sig.params)
            except AttributeError:
                # Workaround for #136: https://github.com/jonathanslenders/ptpython/issues/136
                # AttributeError: 'Lambda' object has no attribute 'get_subscope_by_name'
                return []

            for i, p in enumerated_params:
                # Workaround for #47: 'p' is None when we hit the '*' in the signature.
                #                     and sig has no 'index' attribute.
                # See: https://github.com/jonathanslenders/ptpython/issues/47
                #      https://github.com/davidhalter/jedi/issues/598
                description = (p.description if p else '*') #or '*'
                sig_index = getattr(sig, 'index', 0)

                if i == sig_index:
                    # Note: we use `_Param.description` instead of
                    #       `_Param.name`, that way we also get the '*' before args.
                    append((Signature + ',current-name', str(description)))
                else:
                    append((Signature, str(description)))
                append((Signature + ',operator', ', '))

            if sig.params:
                # Pop last comma
                result.pop()

            append((Signature + ',operator', ')'))
            append((Signature, ' '))
        return result

    return ConditionalContainer(
        content=Window(
            FormattedTextControl(get_text_fragments),
            height=Dimension.exact(1)),
        filter=
            # Show only when there is a signature
            HasSignature(python_input) &
            # And there are no completions to be shown. (would cover signature pop-up.)
            ~(has_completions & (show_completions_menu(python_input) |
                                   show_multi_column_completions_menu(python_input)))
            # Signature needs to be shown.
            & ShowSignature(python_input) &
            # Not done yet.
            ~is_done)


class PythonPromptMargin(PromptMargin):
    """
    Create margin that displays the prompt.
    It shows something like "In [1]:".
    """
    def __init__(self, python_input):
        self.python_input = python_input

        def get_prompt_style():
            return python_input.all_prompt_styles[python_input.prompt_style]

        def get_prompt():
            return to_formatted_text(get_prompt_style().in_prompt())

        def get_continuation(width, line_number, is_soft_wrap):
            if python_input.show_line_numbers and not is_soft_wrap:
                text = ('%i ' % (line_number + 1)).rjust(width)
                return [('class:line-number', text)]
            else:
                return get_prompt_style().in2_prompt(width)

        super(PythonPromptMargin, self).__init__(get_prompt, get_continuation)


def status_bar(python_input):
    """
    Create the `Layout` for the status bar.
    """
    TB = 'class:status-toolbar'

    @if_mousedown
    def toggle_paste_mode(mouse_event):
        python_input.paste_mode = not python_input.paste_mode

    @if_mousedown
    def enter_history(mouse_event):
        python_input.enter_history()

    def get_text_fragments():
        python_buffer = python_input.default_buffer

        result = []
        append = result.append

        append((TB, ' '))
        result.extend(get_inputmode_fragments(python_input))
        append((TB, ' '))

        # Position in history.
        append((TB, '%i/%i ' % (python_buffer.working_index + 1,
                                len(python_buffer._working_lines))))

        # Shortcuts.
        app = get_app()
        if not python_input.vi_mode and app.current_buffer == python_input.search_buffer:
            append((TB, '[Ctrl-G] Cancel search [Enter] Go to this position.'))
        elif bool(app.current_buffer.selection_state) and not python_input.vi_mode:
            # Emacs cut/copy keys.
            append((TB, '[Ctrl-W] Cut [Meta-W] Copy [Ctrl-Y] Paste [Ctrl-G] Cancel'))
        else:
            result.extend([
                (TB + ' class:key', '[F3]', enter_history),
                (TB, ' History ', enter_history),
                (TB + ' class:key', '[F6]', toggle_paste_mode),
                (TB, ' ', toggle_paste_mode),
            ])

            if python_input.paste_mode:
                append((TB + ' class:paste-mode-on', 'Paste mode (on)', toggle_paste_mode))
            else:
                append((TB, 'Paste mode', toggle_paste_mode))

        return result

    return ConditionalContainer(
            content=Window(content=FormattedTextControl(get_text_fragments), style=TB),
            filter=~is_done & renderer_height_is_known &
                 Condition(lambda: python_input.show_status_bar and
                                      not python_input.show_exit_confirmation))


def get_inputmode_fragments(python_input):
    """
    Return current input mode as a list of (token, text) tuples for use in a
    toolbar.
    """
    app = get_app()
    @if_mousedown
    def toggle_vi_mode(mouse_event):
        python_input.vi_mode = not python_input.vi_mode

    token = 'class:status-toolbar'
    input_mode_t = 'class:status-toolbar.input-mode'

    mode = app.vi_state.input_mode
    result = []
    append = result.append

    append((input_mode_t, '[F4] ', toggle_vi_mode))

    # InputMode
    if python_input.vi_mode:
        recording_register = app.vi_state.recording_register
        if recording_register:
            append((token, ' '))
            append((token + ' class:record', 'RECORD({})'.format(recording_register)))
            append((token, ' - '))

        if bool(app.current_buffer.selection_state):
            if app.current_buffer.selection_state.type == SelectionType.LINES:
                append((input_mode_t, 'Vi (VISUAL LINE)', toggle_vi_mode))
            elif app.current_buffer.selection_state.type == SelectionType.CHARACTERS:
                append((input_mode_t, 'Vi (VISUAL)', toggle_vi_mode))
                append((token, ' '))
            elif app.current_buffer.selection_state.type == 'BLOCK':
                append((input_mode_t, 'Vi (VISUAL BLOCK)', toggle_vi_mode))
                append((token, ' '))
        elif mode in (InputMode.INSERT, 'vi-insert-multiple'):
            append((input_mode_t, 'Vi (INSERT)', toggle_vi_mode))
            append((token, '  '))
        elif mode == InputMode.NAVIGATION:
            append((input_mode_t, 'Vi (NAV)', toggle_vi_mode))
            append((token, '     '))
        elif mode == InputMode.REPLACE:
            append((input_mode_t, 'Vi (REPLACE)', toggle_vi_mode))
            append((token, ' '))
    else:
        if app.emacs_state.is_recording:
            append((token, ' '))
            append((token + ' class:record', 'RECORD'))
            append((token, ' - '))

        append((input_mode_t, 'Emacs', toggle_vi_mode))
        append((token, ' '))

    return result


def show_sidebar_button_info(python_input):
    """
    Create `Layout` for the information in the right-bottom corner.
    (The right part of the status bar.)
    """
    @if_mousedown
    def toggle_sidebar(mouse_event):
        " Click handler for the menu. "
        python_input.show_sidebar = not python_input.show_sidebar

    version = sys.version_info
    tokens = [
        ('class:status-toolbar.key', '[F2]', toggle_sidebar),
        ('class:status-toolbar', ' Menu', toggle_sidebar),
        ('class:status-toolbar', ' - '),
        ('class:status-toolbar.python-version', '%s %i.%i.%i' % (platform.python_implementation(),
                                               version[0], version[1], version[2])),
        ('class:status-toolbar', ' '),
    ]
    width = fragment_list_width(tokens)

    def get_text_fragments():
        # Python version
        return tokens

    return ConditionalContainer(
        content=Window(
            FormattedTextControl(get_text_fragments),
            style='class:status-toolbar',
            height=Dimension.exact(1),
            width=Dimension.exact(width)),
        filter=~is_done & renderer_height_is_known &
            Condition(lambda: python_input.show_status_bar and
                                  not python_input.show_exit_confirmation))


def exit_confirmation(python_input, style='class:exit-confirmation'):
    """
    Create `Layout` for the exit message.
    """
    def get_text_fragments():
        # Show "Do you really want to exit?"
        return [
            (style, '\n %s ([y]/n)' % python_input.exit_message),
            ('[SetCursorPosition]', ''),
            (style, '  \n'),
        ]

    visible = ~is_done & Condition(lambda: python_input.show_exit_confirmation)

    return ConditionalContainer(
        content=Window(FormattedTextControl(get_text_fragments), style=style),   # , has_focus=visible)),
        filter=visible)


def meta_enter_message(python_input):
    """
    Create the `Layout` for the 'Meta+Enter` message.
    """
    def get_text_fragments():
        return [('class:accept-message', ' [Meta+Enter] Execute ')]

    def extra_condition():
        " Only show when... "
        b = python_input.default_buffer

        return (
            python_input.show_meta_enter_message and
            (not b.document.is_cursor_at_the_end or
                python_input.accept_input_on_enter is None) and
            '\n' in b.text)

    visible = ~is_done & has_focus(DEFAULT_BUFFER) & Condition(extra_condition)

    return ConditionalContainer(
        content=Window(FormattedTextControl(get_text_fragments)),
        filter=visible)


class PtPythonLayout(object):
    def __init__(self, python_input, lexer=PythonLexer, extra_body=None,
                 extra_toolbars=None, extra_buffer_processors=None,
                 input_buffer_height=None):
        D = Dimension
        extra_body = [extra_body] if extra_body else []
        extra_toolbars = extra_toolbars or []
        extra_buffer_processors = extra_buffer_processors or []
        input_buffer_height = input_buffer_height or D(min=6)

        search_toolbar = SearchToolbar(python_input.search_buffer)

        def create_python_input_window():
            def menu_position():
                """
                When there is no autocompletion menu to be shown, and we have a
                signature, set the pop-up position at `bracket_start`.
                """
                b = python_input.default_buffer

                if b.complete_state is None and python_input.signatures:
                    row, col = python_input.signatures[0].bracket_start
                    index = b.document.translate_row_col_to_index(row - 1, col)
                    return index

            return Window(
                BufferControl(
                    buffer=python_input.default_buffer,
                    search_buffer_control=search_toolbar.control,
                    lexer=lexer,
                    include_default_input_processors=False,
                    input_processors=[
                        ConditionalProcessor(
                            processor=HighlightIncrementalSearchProcessor(),
                            filter=has_focus(SEARCH_BUFFER) | has_focus(search_toolbar.control),
                        ),
                        HighlightSelectionProcessor(),
                        DisplayMultipleCursors(),
                        # Show matching parentheses, but only while editing.
                        ConditionalProcessor(
                            processor=HighlightMatchingBracketProcessor(chars='[](){}'),
                            filter=has_focus(DEFAULT_BUFFER) & ~is_done &
                                Condition(lambda: python_input.highlight_matching_parenthesis)),
                        ConditionalProcessor(
                            processor=AppendAutoSuggestion(),
                            filter=~is_done)
                    ] + extra_buffer_processors,
                    menu_position=menu_position,

                    # Make sure that we always see the result of an reverse-i-search:
                    preview_search=True,
                ),
                left_margins=[PythonPromptMargin(python_input)],
                # Scroll offsets. The 1 at the bottom is important to make sure
                # the cursor is never below the "Press [Meta+Enter]" message
                # which is a float.
                scroll_offsets=ScrollOffsets(bottom=1, left=4, right=4),
                # As long as we're editing, prefer a minimal height of 6.
                height=(lambda: (
                    None if get_app().is_done or python_input.show_exit_confirmation
                            else input_buffer_height)),
                wrap_lines=Condition(lambda: python_input.wrap_lines),
            )

        sidebar = python_sidebar(python_input)

        root_container = HSplit([
            VSplit([
                HSplit([
                    FloatContainer(
                        content=HSplit(
                            [create_python_input_window()] + extra_body
                        ),
                        floats=[
                            Float(xcursor=True,
                                  ycursor=True,
                                  content=ConditionalContainer(
                                      content=CompletionsMenu(
                                          scroll_offset=(
                                              lambda: python_input.completion_menu_scroll_offset),
                                          max_height=12),
                                      filter=show_completions_menu(python_input))),
                            Float(xcursor=True,
                                  ycursor=True,
                                  content=ConditionalContainer(
                                      content=MultiColumnCompletionsMenu(),
                                      filter=show_multi_column_completions_menu(python_input))),
                            Float(xcursor=True,
                                  ycursor=True,
                                  content=signature_toolbar(python_input)),
                            Float(left=2,
                                  bottom=1,
                                  content=exit_confirmation(python_input)),
                            Float(bottom=0, right=0, height=1,
                                  content=meta_enter_message(python_input),
                                  hide_when_covering_content=True),
                            Float(bottom=1, left=1, right=0, content=python_sidebar_help(python_input)),
                        ]),
                    ArgToolbar(),
                    search_toolbar,
                    SystemToolbar(),
                    ValidationToolbar(),
                    ConditionalContainer(
                        content=CompletionsToolbar(),
                        filter=show_completions_toolbar(python_input)),

                    # Docstring region.
                    ConditionalContainer(
                        content=Window(
                            height=D.exact(1),
                            char='\u2500',
                            style='class:separator'),
                        filter=HasSignature(python_input) & ShowDocstring(python_input) & ~is_done),
                    ConditionalContainer(
                        content=Window(
                            BufferControl(
                                buffer=python_input.docstring_buffer,
                                lexer=SimpleLexer(style='class:docstring'),
                                #lexer=PythonLexer,
                            ),
                            height=D(max=12)),
                        filter=HasSignature(python_input) & ShowDocstring(python_input) & ~is_done),
                ]),
                ConditionalContainer(
                    content=HSplit([
                        sidebar,
                        Window(style='class:sidebar,separator', height=1),
                        python_sidebar_navigation(python_input),
                    ]),
                    filter=ShowSidebar(python_input) & ~is_done)
            ]),
        ] + extra_toolbars + [
            VSplit([
                status_bar(python_input),
                show_sidebar_button_info(python_input),
            ])
        ])

        self.layout = Layout(root_container)
        self.sidebar = sidebar

"""
Creation of the `Layout` instance for the Python input/REPL.
"""
from __future__ import unicode_literals

from prompt_toolkit.enums import DEFAULT_BUFFER, SEARCH_BUFFER
from prompt_toolkit.filters import IsDone, HasCompletions, RendererHeightIsKnown, HasFocus, Condition
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.layout.containers import Window, HSplit, VSplit, FloatContainer, Float, ConditionalContainer, ScrollOffsets
from prompt_toolkit.layout.controls import BufferControl, TokenListControl, FillControl
from prompt_toolkit.layout.dimension import LayoutDimension
from prompt_toolkit.layout.lexers import SimpleLexer
from prompt_toolkit.layout.margins import PromptMargin
from prompt_toolkit.layout.menus import CompletionsMenu, MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import ConditionalProcessor, AppendAutoSuggestion, HighlightSearchProcessor, HighlightSelectionProcessor, HighlightMatchingBracketProcessor, Processor, Transformation
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.layout.toolbars import CompletionsToolbar, ArgToolbar, SearchToolbar, ValidationToolbar, SystemToolbar, TokenListToolbar
from prompt_toolkit.layout.utils import token_list_width
from prompt_toolkit.reactive import Integer
from prompt_toolkit.selection import SelectionType

from .filters import HasSignature, ShowSidebar, ShowSignature, ShowDocstring
from .utils import if_mousedown

from pygments.lexers import PythonLexer
from pygments.token import Token

import platform
import sys

__all__ = (
    'create_layout',
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

        def apply_transformation(self, cli, document, lineno,
                                 source_to_display, tokens):
            return Transformation(tokens)


class CompletionVisualisation:
    " Visualisation method for the completions. "
    NONE = 'none'
    POP_UP = 'pop-up'
    MULTI_COLUMN = 'multi-column'
    TOOLBAR = 'toolbar'


def show_completions_toolbar(python_input):
    return Condition(lambda cli: python_input.completion_visualisation == CompletionVisualisation.TOOLBAR)


def show_completions_menu(python_input):
    return Condition(lambda cli: python_input.completion_visualisation == CompletionVisualisation.POP_UP)


def show_multi_column_completions_menu(python_input):
    return Condition(lambda cli: python_input.completion_visualisation == CompletionVisualisation.MULTI_COLUMN)


def python_sidebar(python_input):
    """
    Create the `Layout` for the sidebar with the configurable options.
    """
    def get_tokens(cli):
        tokens = []
        T = Token.Sidebar

        def append_category(category):
            tokens.extend([
                (T, '  '),
                (T.Title, '   %-36s' % category.title),
                (T, '\n'),
            ])

        def append(index, label, status):
            selected = index == python_input.selected_option_index

            @if_mousedown
            def select_item(cli, mouse_event):
                python_input.selected_option_index = index

            @if_mousedown
            def goto_next(cli, mouse_event):
                " Select item and go to next value. "
                python_input.selected_option_index = index
                option = python_input.selected_option
                option.activate_next()

            token = T.Selected if selected else T

            tokens.append((T, ' >' if selected else '  '))
            tokens.append((token.Label, '%-24s' % label, select_item))
            tokens.append((token.Status, ' ', select_item))
            tokens.append((token.Status, '%s' % status, goto_next))

            if selected:
                tokens.append((Token.SetCursorPosition, ''))

            tokens.append((token.Status, ' ' * (13 - len(status)), goto_next))
            tokens.append((T, '<' if selected else ''))
            tokens.append((T, '\n'))

        i = 0
        for category in python_input.options:
            append_category(category)

            for option in category.options:
                append(i, option.title, '%s' % option.get_current_value())
                i += 1

        tokens.pop()  # Remove last newline.

        return tokens

    class Control(TokenListControl):
        def move_cursor_down(self, cli):
            python_input.selected_option_index += 1

        def move_cursor_up(self, cli):
            python_input.selected_option_index -= 1

    return ConditionalContainer(
        content=Window(
            Control(get_tokens, Char(token=Token.Sidebar),
                has_focus=ShowSidebar(python_input) & ~IsDone()),
            width=LayoutDimension.exact(43),
            height=LayoutDimension(min=3),
            scroll_offsets=ScrollOffsets(top=1, bottom=1)),
        filter=ShowSidebar(python_input) & ~IsDone())


def python_sidebar_navigation(python_input):
    """
    Create the `Layout` showing the navigation information for the sidebar.
    """
    def get_tokens(cli):
        tokens = []
        T = Token.Sidebar

        # Show navigation info.
        tokens.extend([
            (T.Separator, ' ' * 43 + '\n'),
            (T, '    '),
            (T.Key, '[Arrows]'),
            (T, ' '),
            (T.Key.Description, 'Navigate'),
            (T, ' '),
            (T.Key, '[Enter]'),
            (T, ' '),
            (T.Key.Description, 'Hide menu'),
        ])

        return tokens

    return ConditionalContainer(
        content=Window(
            TokenListControl(get_tokens, Char(token=Token.Sidebar)),
            width=LayoutDimension.exact(43),
            height=LayoutDimension.exact(2)),
        filter=ShowSidebar(python_input) & ~IsDone())


def python_sidebar_help(python_input):
    """
    Create the `Layout` for the help text for the current item in the sidebar.
    """
    token = Token.Sidebar.HelpText

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

    def get_tokens(cli):
        return [(token, get_current_description())]

    return ConditionalContainer(
        content=Window(
            TokenListControl(get_tokens, Char(token=token)),
            height=LayoutDimension(min=3)),
        filter=ShowSidebar(python_input) &
               Condition(lambda cli: python_input.show_sidebar_help) & ~IsDone())


def signature_toolbar(python_input):
    """
    Return the `Layout` for the signature.
    """
    def get_tokens(cli):
        result = []
        append = result.append
        Signature = Token.Toolbar.Signature

        if python_input.signatures:
            sig = python_input.signatures[0]  # Always take the first one.

            append((Signature, ' '))
            try:
                append((Signature, sig.full_name))
            except IndexError:
                # Workaround for #37: https://github.com/jonathanslenders/python-prompt-toolkit/issues/37
                # See also: https://github.com/davidhalter/jedi/issues/490
                return []

            append((Signature.Operator, '('))

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
                    append((Signature.CurrentName, str(description)))
                else:
                    append((Signature, str(description)))
                append((Signature.Operator, ', '))

            if sig.params:
                # Pop last comma
                result.pop()

            append((Signature.Operator, ')'))
            append((Signature, ' '))
        return result

    return ConditionalContainer(
        content=Window(
            TokenListControl(get_tokens),
            height=LayoutDimension.exact(1)),
        filter=
            # Show only when there is a signature
            HasSignature(python_input) &
            # And there are no completions to be shown. (would cover signature pop-up.)
            ~(HasCompletions() & (show_completions_menu(python_input) |
                                   show_multi_column_completions_menu(python_input)))
            # Signature needs to be shown.
            & ShowSignature(python_input) &
            # Not done yet.
            ~IsDone())


class PythonPromptMargin(PromptMargin):
    """
    Create margin that displays the prompt.
    It shows something like "In [1]:".
    """
    def __init__(self, python_input):
        self.python_input = python_input

        def get_prompt_style():
            return python_input.all_prompt_styles[python_input.prompt_style]

        def get_prompt(cli):
            return get_prompt_style().in_tokens(cli)

        def get_continuation_prompt(cli, width):
            return get_prompt_style().in2_tokens(cli, width)

        super(PythonPromptMargin, self).__init__(get_prompt, get_continuation_prompt,
                show_numbers=Condition(lambda cli: python_input.show_line_numbers))


def status_bar(key_bindings_manager, python_input):
    """
    Create the `Layout` for the status bar.
    """
    TB = Token.Toolbar.Status

    @if_mousedown
    def toggle_paste_mode(cli, mouse_event):
        python_input.paste_mode = not python_input.paste_mode

    @if_mousedown
    def enter_history(cli, mouse_event):
        python_input.enter_history(cli)

    def get_tokens(cli):
        python_buffer = cli.buffers[DEFAULT_BUFFER]

        result = []
        append = result.append

        append((TB, ' '))
        result.extend(get_inputmode_tokens(cli, python_input))
        append((TB, ' '))

        # Position in history.
        append((TB, '%i/%i ' % (python_buffer.working_index + 1,
                                len(python_buffer._working_lines))))

        # Shortcuts.
        if not python_input.vi_mode and cli.current_buffer_name == SEARCH_BUFFER:
            append((TB, '[Ctrl-G] Cancel search [Enter] Go to this position.'))
        elif bool(cli.current_buffer.selection_state) and not python_input.vi_mode:
            # Emacs cut/copy keys.
            append((TB, '[Ctrl-W] Cut [Meta-W] Copy [Ctrl-Y] Paste [Ctrl-G] Cancel'))
        else:
            result.extend([
                (TB.Key, '[F3]', enter_history),
                (TB, ' History ', enter_history),
                (TB.Key, '[F6]', toggle_paste_mode),
                (TB, ' ', toggle_paste_mode),
            ])

            if python_input.paste_mode:
                append((TB.PasteModeOn, 'Paste mode (on)', toggle_paste_mode))
            else:
                append((TB, 'Paste mode', toggle_paste_mode))

        return result

    return TokenListToolbar(
        get_tokens,
        default_char=Char(token=TB),
        filter=~IsDone() & RendererHeightIsKnown() &
            Condition(lambda cli: python_input.show_status_bar and
                                  not python_input.show_exit_confirmation))


def get_inputmode_tokens(cli, python_input):
    """
    Return current input mode as a list of (token, text) tuples for use in a
    toolbar.

    :param cli: `CommandLineInterface` instance.
    """
    @if_mousedown
    def toggle_vi_mode(cli, mouse_event):
        python_input.vi_mode = not python_input.vi_mode

    token = Token.Toolbar.Status

    mode = cli.vi_state.input_mode
    result = []
    append = result.append

    append((token.InputMode, '[F4] ', toggle_vi_mode))

    # InputMode
    if python_input.vi_mode:
        if bool(cli.current_buffer.selection_state):
            if cli.current_buffer.selection_state.type == SelectionType.LINES:
                append((token.InputMode, 'Vi (VISUAL LINE)', toggle_vi_mode))
            elif cli.current_buffer.selection_state.type == SelectionType.CHARACTERS:
                append((token.InputMode, 'Vi (VISUAL)', toggle_vi_mode))
                append((token, ' '))
        elif mode == InputMode.INSERT:
            append((token.InputMode, 'Vi (INSERT)', toggle_vi_mode))
            append((token, '  '))
        elif mode == InputMode.NAVIGATION:
            append((token.InputMode, 'Vi (NAV)', toggle_vi_mode))
            append((token, '     '))
        elif mode == InputMode.REPLACE:
            append((token.InputMode, 'Vi (REPLACE)', toggle_vi_mode))
            append((token, ' '))
    else:
        append((token.InputMode, 'Emacs', toggle_vi_mode))
        append((token, ' '))

    return result


def show_sidebar_button_info(python_input):
    """
    Create `Layout` for the information in the right-bottom corner.
    (The right part of the status bar.)
    """
    @if_mousedown
    def toggle_sidebar(cli, mouse_event):
        " Click handler for the menu. "
        python_input.show_sidebar = not python_input.show_sidebar

    token = Token.Toolbar.Status

    version = sys.version_info
    tokens = [
        (token.Key, '[F2]', toggle_sidebar),
        (token, ' Menu', toggle_sidebar),
        (token, ' - '),
        (token.PythonVersion, '%s %i.%i.%i' % (platform.python_implementation(),
                                               version[0], version[1], version[2])),
        (token, ' '),
    ]
    width = token_list_width(tokens)

    def get_tokens(cli):
        # Python version
        return tokens

    return ConditionalContainer(
        content=Window(
            TokenListControl(get_tokens, default_char=Char(token=token)),
            height=LayoutDimension.exact(1),
            width=LayoutDimension.exact(width)),
        filter=~IsDone() & RendererHeightIsKnown() &
            Condition(lambda cli: python_input.show_status_bar and
                                  not python_input.show_exit_confirmation))


def exit_confirmation(python_input, token=Token.ExitConfirmation):
    """
    Create `Layout` for the exit message.
    """
    def get_tokens(cli):
        # Show "Do you really want to exit?"
        return [
            (token, '\n %s ([y]/n)' % python_input.exit_message),
            (Token.SetCursorPosition, ''),
            (token, '  \n'),
        ]

    visible = ~IsDone() & Condition(lambda cli: python_input.show_exit_confirmation)

    return ConditionalContainer(
        content=Window(TokenListControl(
            get_tokens, default_char=Char(token=token), has_focus=visible)),
        filter=visible)


def meta_enter_message(python_input):
    """
    Create the `Layout` for the 'Meta+Enter` message.
    """
    def get_tokens(cli):
        return [(Token.AcceptMessage, ' [Meta+Enter] Execute ')]

    def extra_condition(cli):
        " Only show when... "
        b = cli.buffers[DEFAULT_BUFFER]

        return (
            python_input.show_meta_enter_message and
            (not b.document.is_cursor_at_the_end or
                python_input.accept_input_on_enter is None) and
            b.is_multiline())

    visible = ~IsDone() & HasFocus(DEFAULT_BUFFER) & Condition(extra_condition)

    return ConditionalContainer(
        content=Window(TokenListControl(get_tokens)),
        filter=visible)


def create_layout(python_input, key_bindings_manager,
                  lexer=PythonLexer,
                  extra_body=None, extra_toolbars=None,
                  extra_buffer_processors=None, input_buffer_height=None):
    D = LayoutDimension
    extra_body = [extra_body] if extra_body else []
    extra_toolbars = extra_toolbars or []
    extra_buffer_processors = extra_buffer_processors or []
    input_buffer_height = input_buffer_height or D(min=6)

    def create_python_input_window():
        def menu_position(cli):
            """
            When there is no autocompletion menu to be shown, and we have a signature,
            set the pop-up position at `bracket_start`.
            """
            b = cli.buffers[DEFAULT_BUFFER]

            if b.complete_state is None and python_input.signatures:
                row, col = python_input.signatures[0].bracket_start
                index = b.document.translate_row_col_to_index(row - 1, col)
                return index

        return Window(
            BufferControl(
                buffer_name=DEFAULT_BUFFER,
                lexer=lexer,
                input_processors=[
                    ConditionalProcessor(
                        processor=HighlightSearchProcessor(preview_search=True),
                        filter=HasFocus(SEARCH_BUFFER),
                    ),
                    HighlightSelectionProcessor(),
                    DisplayMultipleCursors(DEFAULT_BUFFER),
                    # Show matching parentheses, but only while editing.
                    ConditionalProcessor(
                        processor=HighlightMatchingBracketProcessor(chars='[](){}'),
                        filter=HasFocus(DEFAULT_BUFFER) & ~IsDone() &
                            Condition(lambda cli: python_input.highlight_matching_parenthesis)),
                    ConditionalProcessor(
                        processor=AppendAutoSuggestion(),
                        filter=~IsDone())
                ] + extra_buffer_processors,
                menu_position=menu_position,

                # Make sure that we always see the result of an reverse-i-search:
                preview_search=True,
            ),
            left_margins=[PythonPromptMargin(python_input)],
            # Scroll offsets. The 1 at the bottom is important to make sure the
            # cursor is never below the "Press [Meta+Enter]" message which is a float.
            scroll_offsets=ScrollOffsets(bottom=1, left=4, right=4),
            # As long as we're editing, prefer a minimal height of 6.
            get_height=(lambda cli: (
                None if cli.is_done or python_input.show_exit_confirmation
                        else input_buffer_height)),
            wrap_lines=Condition(lambda cli: python_input.wrap_lines),
        )

    return HSplit([
        VSplit([
            HSplit([
                FloatContainer(
                    content=HSplit(
                        [create_python_input_window()] + extra_body
                    ),
                    floats=[
                        Float(xcursor=True,
                              ycursor=True,
                              content=CompletionsMenu(
                                  scroll_offset=Integer.from_callable(
                                      lambda: python_input.completion_menu_scroll_offset),
                                  max_height=12,
                                  extra_filter=show_completions_menu(python_input))),
                        Float(xcursor=True,
                              ycursor=True,
                              content=MultiColumnCompletionsMenu(
                                  extra_filter=show_multi_column_completions_menu(python_input))),
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
                SearchToolbar(),
                SystemToolbar(),
                ValidationToolbar(),
                CompletionsToolbar(extra_filter=show_completions_toolbar(python_input)),

                # Docstring region.
                ConditionalContainer(
                    content=Window(height=D.exact(1),
                                   content=FillControl('\u2500', token=Token.Separator)),
                    filter=HasSignature(python_input) & ShowDocstring(python_input) & ~IsDone()),
                ConditionalContainer(
                    content=Window(
                        BufferControl(
                            buffer_name='docstring',
                            lexer=SimpleLexer(default_token=Token.Docstring),
                            #lexer=PythonLexer,
                        ),
                        height=D(max=12)),
                    filter=HasSignature(python_input) & ShowDocstring(python_input) & ~IsDone(),
                ),
            ]),
            HSplit([
                python_sidebar(python_input),
                python_sidebar_navigation(python_input),
            ])
        ]),
    ] + extra_toolbars + [
        VSplit([
            status_bar(key_bindings_manager, python_input),
            show_sidebar_button_info(python_input),
        ])
    ])

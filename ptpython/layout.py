from __future__ import unicode_literals

from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import IsDone, HasCompletions, RendererHeightIsKnown, Always, HasFocus, Condition
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.layout import Window, HSplit, VSplit, FloatContainer, Float
from prompt_toolkit.layout.controls import BufferControl, TokenListControl, FillControl
from prompt_toolkit.layout.dimension import LayoutDimension
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.processors import HighlightSearchProcessor, HighlightSelectionProcessor, HighlightMatchingBracketProcessor, ConditionalProcessor
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.layout.toolbars import CompletionsToolbar, ArgToolbar, SearchToolbar, ValidationToolbar, SystemToolbar, TokenListToolbar
from prompt_toolkit.layout.utils import token_list_width
from prompt_toolkit.selection import SelectionType

from ptpython.filters import HasSignature, ShowCompletionsMenu, ShowCompletionsToolbar, ShowSidebar, ShowLineNumbersFilter, ShowSignature, ShowDocstring

from pygments.lexers import PythonLexer
from pygments.token import Token

import platform
import sys

__all__ = (
    'create_layout',
)


class PythonSidebar(Window):
    """
    Sidebar containing the configurable options.
    """
    def __init__(self, python_input):
        def get_tokens(cli):
            tokens = []
            T = Token.Sidebar

            def append_category(category):
                tokens.extend([
                    (T, '  '),
                    (T.Title, '   %-36s' % category.title),
                    (T, '\n'),
                ])

            def append(selected, label, status):
                token = T.Selected if selected else T

                tokens.append((T, ' >' if selected else '  '))
                tokens.append((token.Label, '%-24s' % label))
                tokens.append((token.Status, ' '))
                tokens.append((token.Status, '%s' % status))

                if selected:
                    tokens.append((Token.SetCursorPosition, ''))

                tokens.append((token.Status, ' ' * (14 - len(status))))
                tokens.append((T, '<' if selected else ''))
                tokens.append((T, '\n'))

            i = 0
            for category in python_input.options:
                append_category(category)

                for option in category.options:
                    append(i == python_input.selected_option_index,
                           option.description, '%s' % option.get_current_value())
                    i += 1

            tokens.pop()  # Remove last newline.

            return tokens

        super(PythonSidebar, self).__init__(
            TokenListControl(get_tokens, Char(token=Token.Sidebar),
                has_focus=ShowSidebar(python_input) & ~IsDone()),
            width=LayoutDimension.exact(43),
            height=LayoutDimension(min=3),
            scroll_offset=1,
            filter=ShowSidebar(python_input) & ~IsDone())


class PythonSidebarNavigation(Window):
    """
    Showing the navigation information for the sidebar.
    """
    def __init__(self, python_input):
        def get_tokens(cli):
            tokens = []
            T = Token.Sidebar

            # Show navigation info.
            tokens.extend([
                (T, '     '),
                (T.Keys, '[Arrows]'),
                (T.Keys.Description, 'Navigate'),
                (T, ' '),
                (T.Keys, '[Enter]'),
                (T.Keys.Description, 'Hide menu'),
            ])

            return tokens

        super(PythonSidebarNavigation, self).__init__(
            TokenListControl(get_tokens, Char(token=Token.Sidebar)),
            width=LayoutDimension.exact(43),
            height=LayoutDimension.exact(1),
            filter=ShowSidebar(python_input) & ~IsDone())


class SignatureToolbar(Window):
    def __init__(self, python_input):
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

                for i, p in enumerate(sig.params):
                    if i == sig.index:
                        # Note: we use `_Param.description` instead of
                        #       `_Param.name`, that way we also get the '*' before args.
                        append((Signature.CurrentName, str(p.description)))
                    else:
                        append((Signature, str(p.description)))
                    append((Signature.Operator, ', '))

                if sig.params:
                    # Pop last comma
                    result.pop()

                append((Signature.Operator, ')'))
                append((Signature, ' '))
            return result

        super(SignatureToolbar, self).__init__(
            TokenListControl(get_tokens),
            height=LayoutDimension.exact(1),
            filter=
                # Show only when there is a signature
                HasSignature(python_input) &
                # And there are no completions to be shown. (would cover signature pop-up.)
                (~HasCompletions() | ~ShowCompletionsMenu(python_input))
                # Signature needs to be shown.
                & ShowSignature(python_input) &
                # Not done yet.
                ~IsDone())


class PythonPrompt(TokenListControl):
    """
    Prompt showing something like "In [1]:".
    """
    def __init__(self, python_input):
        def get_tokens(cli):
            return [
                (Token.In, 'In ['),
                (Token.In.Number, '%s' % python_input.current_statement_index),
                (Token.In, ']: '),
            ]

        super(PythonPrompt, self).__init__(get_tokens)


class PythonToolbar(TokenListToolbar):
    def __init__(self, key_bindings_manager, python_input, token=Token.Toolbar.Status):
        def get_tokens(cli):
            python_buffer = cli.buffers['default']

            TB = token
            result = []
            append = result.append

            append((TB, ' '))
            result.extend(get_inputmode_tokens(TB, key_bindings_manager, python_input, cli))
            append((TB, '  '))

            # Position in history.
            append((TB, '%i/%i ' % (python_buffer.working_index + 1,
                                    len(python_buffer._working_lines))))

            # Shortcuts.
            if not python_input.vi_mode and cli.focus_stack.current == 'search':
                append((TB, '[Ctrl-G] Cancel search [Enter] Go to this position.'))
            elif bool(cli.current_buffer.selection_state) and not python_input.vi_mode:
                # Emacs cut/copy keys.
                append((TB, '[Ctrl-W] Cut [Meta-W] Copy [Ctrl-Y] Paste [Ctrl-G] Cancel'))
            else:
                append((TB, '  '))

                if python_input.paste_mode:
                    append((TB.On, '[F6] Paste mode (on)   '))
                else:
                    append((TB.Off, '[F6] Paste mode (off)  '))

                if python_buffer.is_multiline():
                    append((TB, ' [Meta+Enter] Execute'))

            return result

        super(PythonToolbar, self).__init__(
            get_tokens,
            default_char=Char(token=token),
            filter=~IsDone() & RendererHeightIsKnown() &
                Condition(lambda cli: python_input.show_status_bar and
                                      not python_input.show_exit_confirmation))


def get_inputmode_tokens(token, key_bindings_manager, python_input, cli):
    """
    Return current input mode as a list of (token, text) tuples for use in a
    toolbar.

    :param cli: `CommandLineInterface` instance.
    """
    mode = key_bindings_manager.vi_state.input_mode
    result = []
    append = result.append

    append((token.InputMode, '[F4] '))

    # InputMode
    if python_input.vi_mode:
        if bool(cli.current_buffer.selection_state):
            if cli.current_buffer.selection_state.type == SelectionType.LINES:
                append((token.InputMode, 'Vi (VISUAL LINE)'))
                append((token, ' '))
            elif cli.current_buffer.selection_state.type == SelectionType.CHARACTERS:
                append((token.InputMode, 'Vi (VISUAL)'))
                append((token, ' '))
        elif mode == InputMode.INSERT:
            append((token.InputMode, 'Vi (INSERT)'))
            append((token, '  '))
        elif mode == InputMode.NAVIGATION:
            append((token.InputMode, 'Vi (NAV)'))
            append((token, '     '))
        elif mode == InputMode.REPLACE:
            append((token.InputMode, 'Vi (REPLACE)'))
            append((token, ' '))
    else:
        append((token.InputMode, 'Emacs'))
        append((token, ' '))

    return result


class ShowSidebarButtonInfo(Window):
    def __init__(self, python_input):
        token = Token.Toolbar.Status

        version = sys.version_info
        tokens = [
            (token, ' [F2] Options'),
            (token, ' - '),
            (token.PythonVersion, '%s %i.%i.%i' % (platform.python_implementation(),
                                                   version[0], version[1], version[2])),
            (token, ' '),
        ]
        width = token_list_width(tokens)

        def get_tokens(cli):
            # Python version
            return tokens

        super(ShowSidebarButtonInfo, self).__init__(
            TokenListControl(get_tokens, default_char=Char(token=token)),
            filter=~IsDone() & RendererHeightIsKnown() &
                Condition(lambda cli: python_input.show_status_bar and
                                      not python_input.show_exit_confirmation),
            height=LayoutDimension.exact(1),
            width=LayoutDimension.exact(width))


class ExitConfirmation(Window):
    """
    Display exit message.
    """
    def __init__(self, python_input, token=Token.ExitConfirmation):
        def get_tokens(cli):
            return [
                (token, '\n Do you really want to exit? ([y]/n)'),
                (Token.SetCursorPosition, ''),
                (token, '  \n'),
            ]

        visible = ~IsDone() & Condition(lambda cli: python_input.show_exit_confirmation)

        super(ExitConfirmation, self).__init__(
            TokenListControl(get_tokens, default_char=Char(token=token),
                             has_focus=visible),
            filter=visible)


def create_layout(python_input, key_bindings_manager,
                  python_prompt_control=None, lexer=PythonLexer, extra_sidebars=None,
                  extra_buffer_processors=None):
    D = LayoutDimension
    extra_sidebars = extra_sidebars or []
    extra_buffer_processors = extra_buffer_processors or []

    def create_python_input_window():
        def menu_position(cli):
            """
            When there is no autocompletion menu to be shown, and we have a signature,
            set the pop-up position at `bracket_start`.
            """
            b = cli.buffers['default']

            if b.complete_state is None and python_input.signatures:
                row, col = python_input.signatures[0].bracket_start
                index = b.document.translate_row_col_to_index(row - 1, col)
                return index

        return Window(
            BufferControl(
                buffer_name=DEFAULT_BUFFER,
                lexer=lexer,
                show_line_numbers=ShowLineNumbersFilter(python_input),
                input_processors=[
                                  # Show matching parentheses, but only while editing.
                                  ConditionalProcessor(
                                      processor=HighlightMatchingBracketProcessor(chars='[](){}'),
                                      filter=HasFocus(DEFAULT_BUFFER) & ~IsDone()),
                                  HighlightSearchProcessor(preview_search=Always()),
                                  HighlightSelectionProcessor()] + extra_buffer_processors,
                menu_position=menu_position,

                # Make sure that we always see the result of an reverse-i-search:
                preview_search=Always(),
            ),
            # As long as we're editing, prefer a minimal height of 6.
            get_height=(lambda cli: (None if cli.is_done else D(min=6))),
        )

    return HSplit([
        VSplit([
            HSplit([
                FloatContainer(
                    content=HSplit([
                        VSplit([
                            Window(
                                python_prompt_control,
                                dont_extend_width=True,
                            ),
                            create_python_input_window(),
                        ]),
                    ]),
                    floats=[
                        Float(xcursor=True,
                              ycursor=True,
                              content=CompletionsMenu(
                                  max_height=12,
                                  extra_filter=ShowCompletionsMenu(python_input))),
                        Float(xcursor=True,
                              ycursor=True,
                              content=SignatureToolbar(python_input)),
                        Float(left=2,
                              bottom=1,
                              content=ExitConfirmation(python_input)),
                    ]),
                ArgToolbar(),
                SearchToolbar(),
                SystemToolbar(),
                ValidationToolbar(),
                CompletionsToolbar(extra_filter=ShowCompletionsToolbar(python_input)),

                # Docstring region.
                Window(height=D.exact(1),
                       content=FillControl('\u2500', token=Token.Separator),
                       filter=HasSignature(python_input) & ShowDocstring(python_input) & ~IsDone()),
                Window(
                    BufferControl(
                        buffer_name='docstring',
                        default_token=Token.Docstring,
                        #lexer=PythonLexer,
                    ),
                    filter=HasSignature(python_input) & ShowDocstring(python_input) & ~IsDone(),
                    height=D(max=12),
                ),
            ]),
            ] + extra_sidebars + [
            HSplit([
                PythonSidebar(python_input),
                PythonSidebarNavigation(python_input),
            ])
        ]),
        VSplit([
            PythonToolbar(key_bindings_manager, python_input),
            ShowSidebarButtonInfo(python_input),
        ])
    ])

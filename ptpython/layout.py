from __future__ import unicode_literals

from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import IsDone, HasCompletions, RendererHeightIsKnown, Always, HasFocus
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


class PythonSidebarControl(TokenListControl):
    def __init__(self, settings, key_bindings_manager):
        def get_tokens(cli):
            tokens = []
            TB = Token.Sidebar

            if key_bindings_manager.enable_vi_mode:
                mode = 'vi'
            else:
                mode = 'emacs'

            if settings.show_completions_toolbar:
                completion_style = 'toolbar'
            elif settings.show_completions_menu:
                completion_style = 'pop-up'
            else:
                completion_style = 'off'

            def append(shortcut, label, status):
                tokens.append((TB.Shortcut, ' [%s] ' % shortcut))
                tokens.append((TB.Label, '%-21s' % label))
                if status:
                    tokens.append((TB.Status, '%9s\n' % status))
                else:
                    tokens.append((TB.Label, '\n'))

            append('F3', 'Completion menu', '(%s)' % completion_style)
            append('F4', 'Input mode', '(%s)' % mode)
            append('F5', 'Complete while typing', '(on)' if settings.complete_while_typing else '(off)')
            append('F6', 'Paste mode', '(on)' if settings.paste_mode else '(off)')
            append('F8', 'Show signature', '(on)' if settings.show_signature else '(off)')
            append('F9', 'Show docstring', '(on)' if settings.show_docstring else '(off)')
            append('F10', 'Show line numbers', '(on)' if settings.show_line_numbers else '(off)')

            return tokens

        super(PythonSidebarControl, self).__init__(get_tokens, Char(token=Token.Sidebar))


class PythonSidebar(Window):
    def __init__(self, settings, key_bindings_manager):
        super(PythonSidebar, self).__init__(
            PythonSidebarControl(settings, key_bindings_manager),
            width=LayoutDimension.exact(37),
            filter=ShowSidebar(settings) & ~IsDone())


class SignatureControl(TokenListControl):
    def __init__(self, settings):
        def get_tokens(cli):
            result = []
            append = result.append
            Signature = Token.Toolbar.Signature

            if settings.signatures:
                sig = settings.signatures[0]  # Always take the first one.

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

        super(SignatureControl, self).__init__(get_tokens)


class SignatureToolbar(Window):
    def __init__(self, settings):
        super(SignatureToolbar, self).__init__(
            SignatureControl(settings),
            height=LayoutDimension.exact(1),
            filter=
                # Show only when there is a signature
                HasSignature(settings) &
                # And there are no completions to be shown. (would cover signature pop-up.)
                (~HasCompletions() | ~ShowCompletionsMenu(settings))
                # Signature needs to be shown.
                & ShowSignature(settings) &
                # Not done yet.
                ~IsDone())


class PythonPrompt(TokenListControl):
    """
    Prompt showing something like "In [1]:".
    """
    def __init__(self, settings):
        def get_tokens(cli):
            return [(Token.Layout.Prompt, 'In [%s]: ' % settings.current_statement_index)]

        super(PythonPrompt, self).__init__(get_tokens)


class PythonToolbar(TokenListToolbar):
    def __init__(self, key_bindings_manager, settings, token=Token.Toolbar.Status):
        def get_tokens(cli):
            python_buffer = cli.buffers['default']

            TB = token
            result = []
            append = result.append

            append((TB, ' '))
            result.extend(get_inputmode_tokens(TB, key_bindings_manager, cli))
            append((TB, '  '))

            # Position in history.
            append((TB, '%i/%i ' % (python_buffer.working_index + 1,
                                    len(python_buffer._working_lines))))

            # Shortcuts.
            if not key_bindings_manager.enable_vi_mode and cli.focus_stack.current == 'search':
                append((TB, '[Ctrl-G] Cancel search [Enter] Go to this position.'))
            elif bool(cli.current_buffer.selection_state) and not key_bindings_manager.enable_vi_mode:
                # Emacs cut/copy keys.
                append((TB, '[Ctrl-W] Cut [Meta-W] Copy [Ctrl-Y] Paste [Ctrl-G] Cancel'))
            else:
                append((TB, '  '))

                if settings.paste_mode:
                    append((TB.On, '[F6] Paste mode (on)   '))
                else:
                    append((TB.Off, '[F6] Paste mode (off)  '))

                if python_buffer.is_multiline():
                    append((TB, ' [Meta+Enter] Execute'))

            return result

        super(PythonToolbar, self).__init__(
            get_tokens,
            default_char=Char(token=token),
            filter=~IsDone() & RendererHeightIsKnown())


def get_inputmode_tokens(token, key_bindings_manager, cli):
    """
    Return current input mode as a list of (token, text) tuples for use in a
    toolbar.

    :param vi_mode: (bool) True when vi mode is enabled.
    :param cli: `CommandLineInterface` instance.
    """
    mode = key_bindings_manager.vi_state.input_mode
    result = []
    append = result.append

    append((token.InputMode, '[F4] '))

    # InputMode
    if key_bindings_manager.enable_vi_mode:
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
    def __init__(self):
        token = Token.Toolbar.Status

        version = sys.version_info
        tokens = [
            (token, ' [F2] Sidebar'),
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
            filter=~IsDone() & RendererHeightIsKnown(),
            height=LayoutDimension.exact(1),
            width=LayoutDimension.exact(width))


def create_layout(settings, key_bindings_manager,
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

            if b.complete_state is None and settings.signatures:
                row, col = settings.signatures[0].bracket_start
                index = b.document.translate_row_col_to_index(row - 1, col)
                return index

        return Window(
            BufferControl(
                buffer_name=DEFAULT_BUFFER,
                lexer=lexer,
                show_line_numbers=ShowLineNumbersFilter(settings, 'default'),
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
                                  extra_filter=ShowCompletionsMenu(settings))),
                        Float(xcursor=True,
                              ycursor=True,
                              content=SignatureToolbar(settings))
                    ]),
                ArgToolbar(),
                SearchToolbar(),
                SystemToolbar(),
                ValidationToolbar(),
                CompletionsToolbar(extra_filter=ShowCompletionsToolbar(settings)),

                # Docstring region.
                Window(height=D.exact(1),
                       content=FillControl('\u2500', token=Token.Separator),
                       filter=HasSignature(settings) & ShowDocstring(settings) & ~IsDone()),
                Window(
                    BufferControl(
                        buffer_name='docstring',
                        default_token=Token.Docstring,
                        #lexer=PythonLexer,
                    ),
                    filter=HasSignature(settings) & ShowDocstring(settings) & ~IsDone(),
                    height=D(max=12),
                ),
            ]),
            ] + extra_sidebars + [
            PythonSidebar(settings, key_bindings_manager),
        ]),
        VSplit([
            PythonToolbar(key_bindings_manager, settings),
            ShowSidebarButtonInfo(),
        ])
    ])

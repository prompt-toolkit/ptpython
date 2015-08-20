#!/usr/bin/env python
"""
Example of embedding a Python REPL, and setting a custom prompt.
"""
from __future__ import unicode_literals

from ptpython.repl import embed
from ptpython.prompt_style import PromptStyle
from pygments.token import Token


def configure(repl):
    # There are several ways to override the prompt.

    # 1. Probably, the best is to add a new PromptStyle to `all_prompt_styles`
    #    and activate it. This way, the other styles are still selectable from
    #    the menu.
    class CustomPrompt(PromptStyle):
        def in_tokens(self, cli):
            return [
                (Token.In, 'Input['),
                (Token.In.Number, '%s' % repl.current_statement_index),
                (Token.In, '] >>: '),
            ]

        def out_tokens(self, cli):
            return [
                (Token.Out, 'Result['),
                (Token.Out.Number, '%s' % repl.current_statement_index),
                (Token.Out, ']: '),
            ]

    repl.all_prompt_styles['custom'] = CustomPrompt()
    repl.prompt_style = 'custom'

    # 2. Assign a new callable to `get_input_prompt_tokens`. This will always take effect.
    ## repl.get_input_prompt_tokens = lambda cli: [(Token.In, '[hello] >>> ')]

    # 3. Also replace `get_input_prompt_tokens`, but still call the original. This inserts
    #    a prefix.

    ## original = repl.get_input_prompt_tokens
    ## repl.get_input_prompt_tokens = lambda cli: [(Token.In, '[prefix]')] + original(cli)


def main():
    embed(globals(), locals(), configure=configure)


if __name__ == '__main__':
    main()

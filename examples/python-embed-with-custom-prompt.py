#!/usr/bin/env python
"""
Example of embedding a Python REPL, and setting a custom prompt.
"""
from prompt_toolkit.formatted_text import HTML, AnyFormattedText

from ptpython.prompt_style import PromptStyle
from ptpython.repl import embed


def configure(repl) -> None:
    # Probably, the best is to add a new PromptStyle to `all_prompt_styles` and
    # activate it. This way, the other styles are still selectable from the
    # menu.
    class CustomPrompt(PromptStyle):
        def in_prompt(self) -> AnyFormattedText:
            return HTML("<ansigreen>Input[%s]</ansigreen>: ") % (
                repl.current_statement_index,
            )

        def in2_prompt(self, width: int) -> AnyFormattedText:
            return "...: ".rjust(width)

        def out_prompt(self) -> AnyFormattedText:
            return HTML("<ansired>Result[%s]</ansired>: ") % (
                repl.current_statement_index,
            )

    repl.all_prompt_styles["custom"] = CustomPrompt()
    repl.prompt_style = "custom"


def main() -> None:
    embed(globals(), locals(), configure=configure)


if __name__ == "__main__":
    main()

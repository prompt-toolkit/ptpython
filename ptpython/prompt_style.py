from __future__ import annotations

import sys
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import AnyFormattedText

if TYPE_CHECKING:
    from .python_input import PythonInput

__all__ = ["PromptStyle", "IPythonPrompt", "ClassicPrompt"]


class PromptStyle(metaclass=ABCMeta):
    """
    Base class for all prompts.

    It will set `sys.ps1` to let some programs know they are run in a REPL.
    See: https://github.com/TylerYep/torchinfo/issues/216
    """
    def __init__(self) -> None:
        sys.ps1 = getattr(sys, "ps1", ">>> ")

    @abstractmethod
    def in_prompt(self) -> AnyFormattedText:
        "Return the input tokens."
        return []

    @abstractmethod
    def in2_prompt(self, width: int) -> AnyFormattedText:
        """
        Tokens for every following input line.

        :param width: The available width. This is coming from the width taken
                      by `in_prompt`.
        """
        return []

    @abstractmethod
    def out_prompt(self) -> AnyFormattedText:
        "Return the output tokens."
        return []


class IPythonPrompt(PromptStyle):
    """
    A prompt resembling the IPython prompt.
    """

    def __init__(self, python_input: PythonInput) -> None:
        super().__init__()
        self.python_input = python_input

    def in_prompt(self) -> AnyFormattedText:
        return [
            ("class:in", "In ["),
            ("class:in.number", f"{self.python_input.current_statement_index}"),
            ("class:in", "]: "),
        ]

    def in2_prompt(self, width: int) -> AnyFormattedText:
        return [("class:in", "...: ".rjust(width))]

    def out_prompt(self) -> AnyFormattedText:
        return [
            ("class:out", "Out["),
            ("class:out.number", f"{self.python_input.current_statement_index}"),
            ("class:out", "]:"),
            ("", " "),
        ]


class ClassicPrompt(PromptStyle):
    """
    The classic Python prompt.
    """

    def in_prompt(self) -> AnyFormattedText:
        return [("class:prompt", ">>> ")]

    def in2_prompt(self, width: int) -> AnyFormattedText:
        return [("class:prompt.dots", "...")]

    def out_prompt(self) -> AnyFormattedText:
        return []

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import StyleAndTextTuples

if TYPE_CHECKING:
    from .python_input import PythonInput

__all__ = ["PromptStyle", "IPythonPrompt", "ClassicPrompt"]


class PromptStyle(metaclass=ABCMeta):
    """
    Base class for all prompts.
    """

    @abstractmethod
    def in_prompt(self) -> StyleAndTextTuples:
        " Return the input tokens. "
        return []

    @abstractmethod
    def in2_prompt(self, width: int) -> StyleAndTextTuples:
        """
        Tokens for every following input line.

        :param width: The available width. This is coming from the width taken
                      by `in_prompt`.
        """
        return []

    @abstractmethod
    def out_prompt(self) -> StyleAndTextTuples:
        " Return the output tokens. "
        return []


class IPythonPrompt(PromptStyle):
    """
    A prompt resembling the IPython prompt.
    """

    def __init__(self, python_input: "PythonInput") -> None:
        self.python_input = python_input

    def in_prompt(self) -> StyleAndTextTuples:
        return [
            ("class:in", "In ["),
            ("class:in.number", "%s" % self.python_input.current_statement_index),
            ("class:in", "]: "),
        ]

    def in2_prompt(self, width: int) -> StyleAndTextTuples:
        return [("class:in", "...: ".rjust(width))]

    def out_prompt(self) -> StyleAndTextTuples:
        return [
            ("class:out", "Out["),
            ("class:out.number", "%s" % self.python_input.current_statement_index),
            ("class:out", "]:"),
            ("", " "),
        ]


class ClassicPrompt(PromptStyle):
    """
    The classic Python prompt.
    """

    def in_prompt(self) -> StyleAndTextTuples:
        return [("class:prompt", ">>> ")]

    def in2_prompt(self, width: int) -> StyleAndTextTuples:
        return [("class:prompt.dots", "...")]

    def out_prompt(self) -> StyleAndTextTuples:
        return []

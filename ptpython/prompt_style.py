from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod
from six import with_metaclass
from pygments.token import Token

__all__ = (
    'PromptStyle',
    'IPythonPrompt',
    'ClassicPrompt',
)


class PromptStyle(with_metaclass(ABCMeta, object)):
    """
    Base class for all prompts.
    """
    @abstractmethod
    def in_tokens(self, cli):
        " Return the input tokens. "
        return []

    @abstractmethod
    def in2_tokens(self, cli, width):
        """
        Tokens for every following input line.

        :param width: The available width. This is coming from the width taken
                      by `in_tokens`.
        """
        return []

    @abstractmethod
    def out_tokens(self, cli):
        " Return the output tokens. "
        return []


class IPythonPrompt(PromptStyle):
    """
    A prompt resembling the IPython prompt.
    """
    def __init__(self, python_input):
        self.python_input = python_input

    def in_tokens(self, cli):
        return [
            (Token.In, 'In ['),
            (Token.In.Number, '%s' % self.python_input.current_statement_index),
            (Token.In, ']: '),
        ]

    def in2_tokens(self, cli, width):
        return [
            (Token.In, '...: '.rjust(width)),
        ]

    def out_tokens(self, cli):
        return [
            (Token.Out, 'Out['),
            (Token.Out.Number, '%s' % self.python_input.current_statement_index),
            (Token.Out, ']:'),
            (Token, ' '),
        ]


class ClassicPrompt(PromptStyle):
    """
    The classic Python prompt.
    """
    def in_tokens(self, cli):
        return [(Token.Prompt, '>>> ')]

    def in2_tokens(self, cli, width):
        return [(Token.Prompt.Dots, '...')]

    def out_tokens(self, cli):
        return []

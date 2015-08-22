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
        return [(Token.In, '>>> ')]

    def out_tokens(self, cli):
        return []

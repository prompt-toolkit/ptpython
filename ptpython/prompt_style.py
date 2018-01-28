from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod
from six import with_metaclass

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
    def in_prompt(self):
        " Return the input tokens. "
        return []

    @abstractmethod
    def in2_prompt(self, width):
        """
        Tokens for every following input line.

        :param width: The available width. This is coming from the width taken
                      by `in_prompt`.
        """
        return []

    @abstractmethod
    def out_prompt(self):
        " Return the output tokens. "
        return []


class IPythonPrompt(PromptStyle):
    """
    A prompt resembling the IPython prompt.
    """
    def __init__(self, python_input):
        self.python_input = python_input

    def in_prompt(self):
        return [
            ('class:in', 'In ['),
            ('class:in.number', '%s' % self.python_input.current_statement_index),
            ('class:in', ']: '),
        ]

    def in2_prompt(self, width):
        return [
            ('class:in', '...: '.rjust(width)),
        ]

    def out_prompt(self):
        return [
            ('class:out', 'Out['),
            ('class:out.number', '%s' % self.python_input.current_statement_index),
            ('class:out', ']:'),
            ('', ' '),
        ]


class ClassicPrompt(PromptStyle):
    """
    The classic Python prompt.
    """
    def in_prompt(self):
        return [('class:prompt', '>>> ')]

    def in2_prompt(self, width):
        return [('class:prompt.dots', '...')]

    def out_prompt(self):
        return []

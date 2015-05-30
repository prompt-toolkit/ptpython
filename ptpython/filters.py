from __future__ import unicode_literals

from prompt_toolkit.filters import Filter

__all__ = (
    'ShowLineNumbersFilter',
    'HasSignature',
    'ShowCompletionsToolbar',
    'ShowCompletionsMenu',
    'ShowSidebar',
    'ShowDocstring',
)


class PythonInputFilter(Filter):
    def __init__(self, python_input):
        self.python_input = python_input

    def __call__(self, cli):
        raise NotImplementedError


class ShowLineNumbersFilter(PythonInputFilter):
    def __call__(self, cli):
        return ('\n' in cli.buffers['default'].text and
                self.python_input.show_line_numbers)


class HasSignature(PythonInputFilter):
    def __call__(self, cli):
        return bool(self.python_input.signatures)


class ShowCompletionsToolbar(PythonInputFilter):
    def __call__(self, cli):
        return self.python_input.show_completions_toolbar


class ShowCompletionsMenu(PythonInputFilter):
    def __call__(self, cli):
        return self.python_input.show_completions_menu and \
            cli.focus_stack.current == 'default'


class ShowSidebar(PythonInputFilter):
    def __call__(self, cli):
        return self.python_input.show_sidebar


class ShowSignature(PythonInputFilter):
    def __call__(self, cli):
        return self.python_input.show_signature


class ShowDocstring(PythonInputFilter):
    def __call__(self, cli):
        return self.python_input.show_docstring

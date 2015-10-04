from __future__ import unicode_literals

from prompt_toolkit.filters import Filter

__all__ = (
    'HasSignature',
    'ShowSidebar',
    'ShowDocstring',
)


class PythonInputFilter(Filter):
    def __init__(self, python_input):
        self.python_input = python_input

    def __call__(self, cli):
        raise NotImplementedError


class HasSignature(PythonInputFilter):
    def __call__(self, cli):
        return bool(self.python_input.signatures)


class ShowSidebar(PythonInputFilter):
    def __call__(self, cli):
        return self.python_input.settings.show_sidebar


class ShowSignature(PythonInputFilter):
    def __call__(self, cli):
        return self.python_input.settings.show_signature


class ShowDocstring(PythonInputFilter):
    def __call__(self, cli):
        return self.python_input.settings.show_docstring

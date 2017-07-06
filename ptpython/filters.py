from __future__ import unicode_literals

from prompt_toolkit.filters import Filter

__all__ = (
    'HasSignature',
    'ShowSidebar',
    'ShowSignature',
    'ShowDocstring',
)


class PythonInputFilter(Filter):
    def __init__(self, python_input):
        self.python_input = python_input

    def __call__(self):
        raise NotImplementedError


class HasSignature(PythonInputFilter):
    def __call__(self):
        return bool(self.python_input.signatures)


class ShowSidebar(PythonInputFilter):
    def __call__(self):
        return self.python_input.show_sidebar


class ShowSignature(PythonInputFilter):
    def __call__(self):
        return self.python_input.show_signature


class ShowDocstring(PythonInputFilter):
    def __call__(self):
        return self.python_input.show_docstring

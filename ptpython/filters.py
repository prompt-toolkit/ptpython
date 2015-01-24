from __future__ import unicode_literals

from prompt_toolkit.filters import Filter

from ptpython.utils import current_python_buffer


class ShowLineNumbersFilter(Filter):
    def __init__(self, settings, buffer_name):
        self.buffer_name = buffer_name
        self.settings = settings

    def __call__(self, cli):
        return ('\n' in cli.buffers[self.buffer_name].text and
                self.settings.show_line_numbers)


class HasSignature(Filter):
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, cli):
        _, python_buffer = current_python_buffer(cli, self.settings)
        return python_buffer is not None and bool(python_buffer.signatures)


class IsPythonBufferFocussed(Filter):
    def __call__(self, cli):
        return cli.focus_stack.current.startswith('python-')


class ShowCompletionsToolbar(Filter):
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, cli):
        return self.settings.show_completions_toolbar


class ShowCompletionsMenu(Filter):
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, cli):
        return self.settings.show_completions_menu


class ShowSidebar(Filter):
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, cli):
        return self.settings.show_sidebar


class ShowSignature(Filter):
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, cli):
        return self.settings.show_signature


class ShowDocstring(Filter):
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, cli):
        return self.settings.show_docstring


class PythonBufferFocussed(Filter):
    """
    True when this python buffer is currently focussed, or -- in case that the
    focus is currently on a search/system buffer -- when it was the last
    focussed buffer.
    """
    def __init__(self, buffer_name, settings):
        self.buffer_name = buffer_name
        self.settings = settings

    def __call__(self, cli):
        name, buffer_instance = current_python_buffer(cli, self.settings)
        return name == self.buffer_name


class HadMultiplePythonBuffers(Filter):
    """
    True when we had a several Python buffers at some point.
    """
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, cli):
        return self.settings.buffer_index > 1

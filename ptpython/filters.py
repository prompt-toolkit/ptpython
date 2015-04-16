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
        return bool(self.settings.signatures)


class ShowCompletionsToolbar(Filter):
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, cli):
        return self.settings.show_completions_toolbar


class ShowCompletionsMenu(Filter):
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, cli):
        return self.settings.show_completions_menu and \
            cli.focus_stack.current == 'default'


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

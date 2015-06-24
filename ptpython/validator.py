from __future__ import unicode_literals

from prompt_toolkit.validation import Validator, ValidationError

__all__ = (
    'PythonValidator',
)


class PythonValidator(Validator):
    """
    Validation of Python input.

    :param get_compiler_flags: Callable that returns the currently
        active compiler flags.
    """
    def __init__(self, get_compiler_flags=None):
        self.get_compiler_flags = get_compiler_flags

    def validate(self, document):
        """
        Check input for Python syntax errors.
        """
        # When the input starts with Ctrl-Z, always accept. This means EOF in a
        # Python REPL.
        if document.text.startswith('\x1a'):
            return

        try:
            if self.get_compiler_flags:
                flags = self.get_compiler_flags()
            else:
                flags = 0

            compile(document.text, '<input>', 'exec', flags=flags, dont_inherit=True)
        except SyntaxError as e:
            # Note, the 'or 1' for offset is required because Python 2.7
            # gives `None` as offset in case of '4=4' as input. (Looks like
            # fixed in Python 3.)
            index = document.translate_row_col_to_index(e.lineno - 1,  (e.offset or 1) - 1)
            raise ValidationError(index, 'Syntax Error')
        except TypeError as e:
            # e.g. "compile() expected string without null bytes"
            raise ValidationError(0, str(e))

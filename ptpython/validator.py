from __future__ import unicode_literals

from prompt_toolkit.validation import Validator, ValidationError


class PythonValidator(Validator):
    def validate(self, document):
        """
        Check input for Python syntax errors.
        """
        try:
            compile(document.text, '<input>', 'exec')
        except SyntaxError as e:
            # Note, the 'or 1' for offset is required because Python 2.7
            # gives `None` as offset in case of '4=4' as input. (Looks like
            # fixed in Python 3.)
            index = document.translate_row_col_to_index(e.lineno - 1,  (e.offset or 1) - 1)
            raise ValidationError(index, 'Syntax Error')
        except TypeError as e:
            # e.g. "compile() expected string without null bytes"
            raise ValidationError(0, str(e))

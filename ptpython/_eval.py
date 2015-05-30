"""
Eval without `unicode_literals` and `print_function`.
"""

__all__ = (
    'eval_',
)


def eval_(source, globals=None, locals=None):
    """
    A wrapper around eval, executing in a new file
    without `unicode_literals`. (For a REPL, we don't want `unicode_literals`
    to propagate through eval.)
    """
    return eval(source, globals, locals)

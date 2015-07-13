"""
Wrapper around the eventloop that gives some time to the Tkinter GUI to process
events when it's loaded and while we are waiting for input at the REPL. This
way we don't block the UI of for instance ``turtle`` and other Tk libraries.

(Normally Tkinter registeres it's callbacks in ``PyOS_InputHook`` to integrate
in readline. ``prompt-toolkit`` doesn't understand that input hook, but this
will fix it for Tk.)
"""
from prompt_toolkit.shortcuts import create_eventloop as _create_eventloop
import sys

__all__ = (
    'create_eventloop',
)

def _inputhook_tk(inputhook_context):
    """
    Inputhook for Tk.
    Run the Tk eventloop until prompt-toolkit needs to process the next input.
    """
    import _tkinter, Tkinter  # Keep this imports inline!

    root = Tkinter._default_root

    if root is not None:
        # Add a handler that sets the stop flag when `prompt-toolkit` has input
        # to process.
        stop = [False]
        def done(*a):
            stop[0] = True

        root.createfilehandler(inputhook_context.fileno(), _tkinter.READABLE, done)

        # Run the TK event loop as long as we don't receive input.
        while root.dooneevent(_tkinter.ALL_EVENTS):
            if stop[0]:
                break

        root.deletefilehandler(inputhook_context.fileno())


def _inputhook(inputhook_context):
    # Only call the real input hook when the 'Tkinter' library was loaded.
    if 'Tkinter' in  sys.modules:
        _inputhook_tk(inputhook_context)


def create_eventloop():
    return _create_eventloop(inputhook=_inputhook)

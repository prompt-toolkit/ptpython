import ast
import keyword
import re
from typing import TYPE_CHECKING, Iterable

from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    PathCompleter,
)
from prompt_toolkit.contrib.regular_languages.compiler import compile as compile_grammar
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.document import Document

from ptpython.utils import get_jedi_script_from_document

if TYPE_CHECKING:
    from prompt_toolkit.contrib.regular_languages.compiler import _CompiledGrammar

__all__ = ["PythonCompleter"]


class PythonCompleter(Completer):
    """
    Completer for Python code.
    """

    def __init__(self, get_globals, get_locals, get_enable_dictionary_completion):
        super().__init__()

        self.get_globals = get_globals
        self.get_locals = get_locals
        self.get_enable_dictionary_completion = get_enable_dictionary_completion

        self.dictionary_completer = DictionaryCompleter(get_globals, get_locals)

        self._path_completer_cache = None
        self._path_completer_grammar_cache = None

    @property
    def _path_completer(self) -> GrammarCompleter:
        if self._path_completer_cache is None:
            self._path_completer_cache = GrammarCompleter(
                self._path_completer_grammar,
                {
                    "var1": PathCompleter(expanduser=True),
                    "var2": PathCompleter(expanduser=True),
                },
            )
        return self._path_completer_cache

    @property
    def _path_completer_grammar(self) -> "_CompiledGrammar":
        """
        Return the grammar for matching paths inside strings inside Python
        code.
        """
        # We make this lazy, because it delays startup time a little bit.
        # This way, the grammar is build during the first completion.
        if self._path_completer_grammar_cache is None:
            self._path_completer_grammar_cache = self._create_path_completer_grammar()
        return self._path_completer_grammar_cache

    def _create_path_completer_grammar(self) -> "_CompiledGrammar":
        def unwrapper(text: str) -> str:
            return re.sub(r"\\(.)", r"\1", text)

        def single_quoted_wrapper(text: str) -> str:
            return text.replace("\\", "\\\\").replace("'", "\\'")

        def double_quoted_wrapper(text: str) -> str:
            return text.replace("\\", "\\\\").replace('"', '\\"')

        grammar = r"""
                # Text before the current string.
                (
                    [^'"#]                                  |  # Not quoted characters.
                    '''  ([^'\\]|'(?!')|''(?!')|\\.])*  ''' |  # Inside single quoted triple strings
                    "" " ([^"\\]|"(?!")|""(?!^)|\\.])* "" " |  # Inside double quoted triple strings

                    \#[^\n]*(\n|$)           |  # Comment.
                    "(?!"") ([^"\\]|\\.)*"   |  # Inside double quoted strings.
                    '(?!'') ([^'\\]|\\.)*'      # Inside single quoted strings.

                        # Warning: The negative lookahead in the above two
                        #          statements is important. If we drop that,
                        #          then the regex will try to interpret every
                        #          triple quoted string also as a single quoted
                        #          string, making this exponentially expensive to
                        #          execute!
                )*
                # The current string that we're completing.
                (
                    ' (?P<var1>([^\n'\\]|\\.)*) |  # Inside a single quoted string.
                    " (?P<var2>([^\n"\\]|\\.)*)    # Inside a double quoted string.
                )
        """

        return compile_grammar(
            grammar,
            escape_funcs={"var1": single_quoted_wrapper, "var2": double_quoted_wrapper},
            unescape_funcs={"var1": unwrapper, "var2": unwrapper},
        )

    def _complete_path_while_typing(self, document: Document) -> bool:
        char_before_cursor = document.char_before_cursor
        return bool(
            document.text
            and (char_before_cursor.isalnum() or char_before_cursor in "/.~")
        )

    def _complete_python_while_typing(self, document: Document) -> bool:
        char_before_cursor = document.char_before_cursor
        return bool(
            document.text
            and (char_before_cursor.isalnum() or char_before_cursor in "_.")
        )

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """
        Get Python completions.
        """
        # Do dictionary key completions.
        if self.get_enable_dictionary_completion():
            has_dict_completions = False
            for c in self.dictionary_completer.get_completions(
                document, complete_event
            ):
                has_dict_completions = True
                yield c
            if has_dict_completions:
                return

        # Do Path completions (if there were no dictionary completions).
        if complete_event.completion_requested or self._complete_path_while_typing(
            document
        ):
            for c in self._path_completer.get_completions(document, complete_event):
                yield c

        # If we are inside a string, Don't do Jedi completion.
        if self._path_completer_grammar.match(document.text_before_cursor):
            return

        # Do Jedi Python completions.
        if complete_event.completion_requested or self._complete_python_while_typing(
            document
        ):
            script = get_jedi_script_from_document(
                document, self.get_locals(), self.get_globals()
            )

            if script:
                try:
                    completions = script.completions()
                except TypeError:
                    # Issue #9: bad syntax causes completions() to fail in jedi.
                    # https://github.com/jonathanslenders/python-prompt-toolkit/issues/9
                    pass
                except UnicodeDecodeError:
                    # Issue #43: UnicodeDecodeError on OpenBSD
                    # https://github.com/jonathanslenders/python-prompt-toolkit/issues/43
                    pass
                except AttributeError:
                    # Jedi issue #513: https://github.com/davidhalter/jedi/issues/513
                    pass
                except ValueError:
                    # Jedi issue: "ValueError: invalid \x escape"
                    pass
                except KeyError:
                    # Jedi issue: "KeyError: u'a_lambda'."
                    # https://github.com/jonathanslenders/ptpython/issues/89
                    pass
                except IOError:
                    # Jedi issue: "IOError: No such file or directory."
                    # https://github.com/jonathanslenders/ptpython/issues/71
                    pass
                except AssertionError:
                    # In jedi.parser.__init__.py: 227, in remove_last_newline,
                    # the assertion "newline.value.endswith('\n')" can fail.
                    pass
                except SystemError:
                    # In jedi.api.helpers.py: 144, in get_stack_at_position
                    # raise SystemError("This really shouldn't happen. There's a bug in Jedi.")
                    pass
                except NotImplementedError:
                    # See: https://github.com/jonathanslenders/ptpython/issues/223
                    pass
                except Exception:
                    # Supress all other Jedi exceptions.
                    pass
                else:
                    for c in completions:
                        yield Completion(
                            c.name_with_symbols,
                            len(c.complete) - len(c.name_with_symbols),
                            display=c.name_with_symbols,
                            style=_get_style_for_name(c.name_with_symbols),
                        )


class DictionaryCompleter(Completer):
    """
    Experimental completer for Python dictionary keys.

    Warning: This does an `eval` on the Python object before the open square
             bracket, which is potentially dangerous. It doesn't match on
             function calls, so it only triggers attribute access.
    """

    def __init__(self, get_globals, get_locals):
        super().__init__()

        self.get_globals = get_globals
        self.get_locals = get_locals

        self.pattern = re.compile(
            r"""
                # Any expression safe enough to eval while typing.
                # No operators, except dot, and only other dict lookups.
                # Technically, this can be unsafe of course, if bad code runs
                # in `__getattr__` or ``__getitem__``.
                (
                    # Variable name
                    [a-zA-Z0-9_]+

                    \s*

                    (?:
                        # Attribute access.
                        \s* \. \s* [a-zA-Z0-9_]+ \s*

                        |

                        # Item lookup.
                        # (We match the square brackets. We don't care about
                        # matching quotes here in the regex. Nested square
                        # brackets are not supported.)
                        \s* \[ [a-zA-Z0-9_'"\s]+ \] \s*
                    )*
                )

                # Dict loopup to complete (square bracket open + start of
                # string).
                \[
                \s* ([a-zA-Z0-9_'"]*)$
            """,
            re.VERBOSE,
        )

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        match = self.pattern.search(document.text_before_cursor)
        if match is not None:
            object_var, key = match.groups()
            object_var = object_var.strip()

            # Do lookup of `object_var` in the context.
            try:
                result = eval(object_var, self.get_globals(), self.get_locals())
            except BaseException:
                return  # Many exception, like NameError can be thrown here.

            # If this object is a dictionary, complete the keys.
            if isinstance(result, dict):
                # Try to evaluate the key.
                key_obj = key
                for k in [key, key + '"', key + "'"]:
                    try:
                        key_obj = ast.literal_eval(k)
                    except (SyntaxError, ValueError):
                        continue
                    else:
                        break

                for k in result:
                    if str(k).startswith(key_obj):
                        yield Completion(str(repr(k)), -len(key), display=str(repr(k)))


try:
    import builtins

    _builtin_names = dir(builtins)
except ImportError:  # Python 2.
    _builtin_names = []


def _get_style_for_name(name: str) -> str:
    """
    Return completion style to use for this name.
    """
    if name in _builtin_names:
        return "class:completion.builtin"

    if keyword.iskeyword(name):
        return "class:completion.keyword"

    return ""

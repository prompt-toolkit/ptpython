from __future__ import annotations

from prompt_toolkit.document import Document

from ptpython.completer import PythonCompleter
from ptpython.utils import get_jedi_script_from_document


def test_complete_path_while_typing_empty_or_whitespace() -> None:
    completer = PythonCompleter(
        get_globals=lambda: {},
        get_locals=lambda: {},
        enable_dictionary_completion=lambda: True,
    )
    # Empty document.
    assert completer._complete_path_while_typing(Document("")) is False
    # Whitespace-only.
    assert completer._complete_path_while_typing(Document("   ")) is False
    # Newline-only.
    assert completer._complete_path_while_typing(Document("\n")) is False
    # Cursor at start of non-empty text.
    assert completer._complete_path_while_typing(Document("hello/", cursor_position=0)) is False


def test_complete_path_while_typing_valid_paths() -> None:
    completer = PythonCompleter(
        get_globals=lambda: {},
        get_locals=lambda: {},
        enable_dictionary_completion=lambda: True,
    )
    assert completer._complete_path_while_typing(Document("hello/")) is True
    assert completer._complete_path_while_typing(Document("~/")) is True
    assert completer._complete_path_while_typing(Document("./")) is True


def test_get_jedi_script_from_document_return_annotation() -> None:
    assert get_jedi_script_from_document.__annotations__["return"] == "Interpreter | None"

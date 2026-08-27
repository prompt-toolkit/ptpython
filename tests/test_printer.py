from __future__ import annotations

from unittest.mock import MagicMock

from prompt_toolkit.formatted_text.utils import split_lines

from ptpython.printer import OutputPrinter


def test_format_result_output_handles_mock_with_fabricated_pt_repr() -> None:
    """A ``unittest.mock.MagicMock`` fabricates any attribute, including
    ``__pt_repr__``, which resolves to more mocks. ``to_formatted_text`` then
    yields malformed fragments (e.g. an empty tuple) that used to crash
    ``split_lines`` with ``ValueError: not enough values to unpack``. The
    printer must fall back to the normal ``repr()`` path instead. See #610.
    """
    mock = MagicMock()
    mock.get()
    call = mock.method_calls[0]

    printer = OutputPrinter.__new__(OutputPrinter)
    fragments = list(
        printer._format_result_output(
            call,
            reformat=False,
            highlight=True,
            line_length=80,
            paginate=False,
        )
    )

    # Every fragment must be a well-formed (style, text) tuple, so splitting
    # into lines does not raise.
    for fragment in fragments:
        assert isinstance(fragment, tuple)
        assert len(fragment) >= 2
    list(split_lines(fragments))

    # The fallback renders the object's ``repr`` rather than the mock's
    # fabricated formatted text.
    rendered = "".join(text for _, text, *_ in fragments)
    assert "call" in rendered

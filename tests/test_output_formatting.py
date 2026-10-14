from __future__ import annotations

import ast
import subprocess
import sys
from io import StringIO

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.styles import DummyStyleTransformation, Style

from ptpython.printer import OutputPrinter
from ptpython.repl import PythonRepl


class RecordingOutput(DummyOutput):
    def __init__(self, columns=20):
        self.columns = columns
        self.stream = StringIO()

    def get_size(self):
        return Size(rows=24, columns=self.columns)

    def write(self, data):
        self.stream.write(data)

    def write_raw(self, data):
        self.stream.write(data)


def display(result, formatter="ruff", reformat=True, columns=20, highlight=False):
    output = RecordingOutput(columns)
    printer = OutputPrinter(
        output=output,
        input=DummyInput(),
        style=Style.from_dict({}),
        title="",
        style_transformation=DummyStyleTransformation(),
    )
    printer.display_result(
        result,
        out_prompt="",
        formatter=formatter,
        reformat=reformat,
        highlight=highlight,
        paginate=False,
    )
    return output.stream.getvalue()


@pytest.mark.parametrize("highlight", [False, True])
def test_ruff_formats_result(highlight):
    pytest.importorskip("ruff")
    value = {"long key": [1, 2, 3], "unicode": "café"}
    text = display(value, highlight=highlight)
    assert text.startswith("{\r\n")
    assert ast.literal_eval(text.strip()) == value


def test_ruff_ignores_project_configuration(tmp_path, monkeypatch):
    pytest.importorskip("ruff")
    (tmp_path / "ruff.toml").write_text("this is not valid TOML")
    monkeypatch.chdir(tmp_path)
    assert ast.literal_eval(display([1, 2]).strip()) == [1, 2]
    assert display([1, 2]).strip() == "[1, 2]"


@pytest.mark.parametrize("columns", [-1, 1, 80, 70000])
def test_ruff_terminal_width(columns):
    pytest.importorskip("ruff")
    assert ast.literal_eval(display(list(range(10)), columns=columns).strip()) == list(
        range(10)
    )


@pytest.mark.parametrize(
    "error", [FileNotFoundError(), subprocess.CalledProcessError(1, "ruff")]
)
def test_ruff_failure_keeps_original_repr(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "run", fail)
    assert display([1, 2, 3]).strip() == repr([1, 2, 3])


def test_ruff_interrupt_propagates(monkeypatch):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, "run", interrupt)
    with pytest.raises(KeyboardInterrupt):
        display([1, 2, 3])


def test_ruff_unavailable_in_python_environment(monkeypatch, tmp_path):
    # Use an isolated interpreter invocation without site-packages.
    original_run = subprocess.run

    def without_packages(args, **kwargs):
        assert args[:3] == [sys.executable, "-m", "ruff"]
        return original_run([sys.executable, "-S", *args[1:]], **kwargs)

    monkeypatch.setattr(subprocess, "run", without_packages)
    monkeypatch.chdir(tmp_path)
    assert display([1, 2, 3]).strip() == repr([1, 2, 3])


def test_no_formatter_for_disabled_or_custom_results(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("formatter should not run")

    class Custom:
        def __pt_repr__(self):
            return [("", "custom output")]

    class NotPython:
        def __repr__(self):
            return "<not Python>"

    monkeypatch.setattr(subprocess, "run", unexpected)
    assert display([1, 2, 3], reformat=False).strip() == "[1, 2, 3]"
    assert display(Custom()).strip() == "custom output"
    assert display(NotPython()).strip() == "<not Python>"
    assert display("x" * 1_000_000).strip() == repr("x" * 1_000_000)


def test_repl_selects_formatter_and_can_switch():
    pytest.importorskip("ruff")
    pytest.importorskip("black")
    output = RecordingOutput()
    repl = PythonRepl(input=DummyInput(), output=output)
    assert repl.output_formatter == "black"
    assert not repl.enable_output_formatting
    repl.enable_output_formatting = True
    option = next(
        option
        for category in repl.options
        for option in category.options
        if option.title == "Output formatter"
    )
    for formatter in ["ruff", "black"]:
        option.values[formatter]()
        assert option.get_current_value() == formatter
        output.stream.truncate(0)
        output.stream.seek(0)
        repl.run_and_show_expression("list(range(10))")
        text = output.stream.getvalue()
        assert "[\r\n" in text
        assert "9," in text


def test_repl_can_format_with_ruff_without_black(monkeypatch):
    pytest.importorskip("ruff")
    monkeypatch.setitem(sys.modules, "black", None)
    output = RecordingOutput()
    repl = PythonRepl(input=DummyInput(), output=output)
    repl.enable_output_formatting = True
    repl.output_formatter = "ruff"
    repl.run_and_show_expression("list(range(10))")
    assert "[\r\n" in output.stream.getvalue()

"""Tests for the terminal tools layer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from aurora.app.core.exceptions import ValidationError
from aurora.app.tools import Permission
from aurora.app.tools.terminal import (
    RunTerminalTool,
    TerminalRunner,
    dangerous_reason,
    terminal_registry,
)

PY = sys.executable

# --- safety ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [["rm", "-rf", "/"], ["dd", "if=/dev/zero"], ["sh", "-c", ":(){ :|:& };:"]],
)
def test_dangerous_commands_flagged(command: list[str]) -> None:
    assert dangerous_reason(command) is not None


@pytest.mark.parametrize("command", [["echo", "hi"], [PY, "-c", "print(1)"], ["ls"]])
def test_safe_commands_not_flagged(command: list[str]) -> None:
    assert dangerous_reason(command) is None


# --- runner ---------------------------------------------------------------


async def test_run_captures_stdout_and_exit_code(tmp_path: Path) -> None:
    runner = TerminalRunner(str(tmp_path))
    result = await runner.run([PY, "-c", "print('hello')"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"
    assert result.timed_out is False
    assert result.duration_seconds >= 0.0


async def test_run_captures_nonzero_exit_and_stderr(tmp_path: Path) -> None:
    runner = TerminalRunner(str(tmp_path))
    result = await runner.run(
        [PY, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"]
    )
    assert result.exit_code == 3
    assert "boom" in result.stderr


async def test_run_times_out(tmp_path: Path) -> None:
    runner = TerminalRunner(str(tmp_path))
    result = await runner.run([PY, "-c", "import time; time.sleep(5)"], timeout=0.5)
    assert result.timed_out is True
    assert result.exit_code == -1


async def test_run_respects_cwd(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    runner = TerminalRunner(str(tmp_path))
    result = await runner.run(
        [PY, "-c", "import os; print(os.path.basename(os.getcwd()))"], cwd="sub"
    )
    assert result.stdout.strip() == "sub"


async def test_run_rejects_bad_cwd(tmp_path: Path) -> None:
    runner = TerminalRunner(str(tmp_path))
    with pytest.raises(ValidationError):
        await runner.run([PY, "-c", "pass"], cwd="does-not-exist")


async def test_stream_yields_lines(tmp_path: Path) -> None:
    runner = TerminalRunner(str(tmp_path))
    lines = [
        line
        async for line in runner.stream([PY, "-c", "print('a'); print('b'); print('c')"])
    ]
    texts = [line.text for line in lines if line.stream == "stdout"]
    assert texts == ["a", "b", "c"]


# --- tool integration -----------------------------------------------------


async def test_registry_exposes_terminal_tools(tmp_path: Path) -> None:
    names = terminal_registry(str(tmp_path)).names()
    assert names == ("run_terminal", "run_tests")


async def test_run_terminal_tool_success(tmp_path: Path) -> None:
    reg = terminal_registry(str(tmp_path))
    result = await reg.invoke("run_terminal", {"command": [PY, "-c", "print('ok')"]})
    assert result.ok is True
    assert result.data["stdout"].strip() == "ok"


async def test_dangerous_requires_confirmation(tmp_path: Path) -> None:
    reg = terminal_registry(str(tmp_path))
    # Contains a dangerous fragment but the executable is a harmless python call.
    args = {"command": [PY, "-c", "print('x')", "/dev/sd"]}
    denied = await reg.invoke("run_terminal", args)
    assert denied.ok is False
    assert denied.error["code"] == "confirmation_required"

    confirmed = await reg.invoke("run_terminal", {**args, "confirm": True})
    assert confirmed.ok is True
    assert confirmed.data["stdout"].strip() == "x"


async def test_empty_command_is_validation_error(tmp_path: Path) -> None:
    reg = terminal_registry(str(tmp_path))
    result = await reg.invoke("run_terminal", {"command": []})
    assert result.ok is False
    assert result.error["code"] == "validation_error"


async def test_execute_permission_enforced(tmp_path: Path) -> None:
    reg = terminal_registry(str(tmp_path))
    denied = await reg.invoke(
        "run_terminal",
        {"command": [PY, "-c", "print(1)"]},
        granted=frozenset({Permission.READ}),
    )
    assert denied.ok is False
    assert denied.error["code"] == "permission_denied"


def test_run_tests_tool_metadata(tmp_path: Path) -> None:
    tool = RunTerminalTool(str(tmp_path))
    assert Permission.EXECUTE in tool.metadata.permissions

"""Async command execution with capture and streaming.

Commands run via ``create_subprocess_exec`` — an argument vector, never a
shell — so shell injection is impossible. The runner captures stdout, stderr,
exit code, and wall-clock duration, and can stream output line by line.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path

from aurora.app.core.exceptions import ToolError, ValidationError
from aurora.app.core.logging import get_logger
from aurora.app.tools.filesystem.paths import PathSandbox
from aurora.app.tools.terminal.models import CommandResult, StreamLine

_logger = get_logger("tools.terminal")


class TerminalRunner:
    """Executes commands within a working-directory sandbox."""

    def __init__(self, workdir: str | Path) -> None:
        self._sandbox = PathSandbox(workdir)

    def _cwd(self, cwd: str | None) -> Path:
        if cwd is None:
            return self._sandbox.root
        resolved = self._sandbox.resolve(cwd)
        if not resolved.is_dir():
            raise ValidationError(f"Working directory does not exist: {cwd}")
        return resolved

    @staticmethod
    def _validate(command: list[str]) -> list[str]:
        if not command or not all(isinstance(part, str) and part for part in command):
            raise ValidationError("Command must be a non-empty list of strings")
        return command

    async def _spawn(self, command: list[str], cwd: Path) -> asyncio.subprocess.Process:
        try:
            return await asyncio.create_subprocess_exec(
                *command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, ValueError) as exc:
            raise ToolError(f"Cannot execute '{command[0]}': {exc}") from exc

    async def run(
        self, command: list[str], cwd: str | None = None, timeout: float = 30.0
    ) -> CommandResult:
        """Run ``command`` to completion, capturing its output.

        Args:
            command: Argument vector; ``command[0]`` is the executable.
            cwd: Working directory relative to the sandbox root.
            timeout: Seconds before the command is killed.

        Returns:
            The captured :class:`CommandResult`.
        """
        argv = self._validate(command)
        target = self._cwd(cwd)
        _logger.info("run", extra={"executable": argv[0], "cwd": str(target)})
        start = time.perf_counter()
        proc = await self._spawn(argv, target)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return CommandResult(
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
                duration_seconds=round(time.perf_counter() - start, 4),
                timed_out=True,
            )
        return CommandResult(
            stdout=out.decode(errors="replace"),
            stderr=err.decode(errors="replace"),
            exit_code=proc.returncode if proc.returncode is not None else -1,
            duration_seconds=round(time.perf_counter() - start, 4),
        )

    async def stream(
        self, command: list[str], cwd: str | None = None
    ) -> AsyncIterator[StreamLine]:
        """Run ``command`` and yield its output line by line as it arrives."""
        argv = self._validate(command)
        proc = await self._spawn(argv, self._cwd(cwd))
        queue: asyncio.Queue[StreamLine | None] = asyncio.Queue()

        async def pump(stream: asyncio.StreamReader, name: str) -> None:
            while raw := await stream.readline():
                text = raw.decode(errors="replace").rstrip("\r\n")
                await queue.put(StreamLine(stream=name, text=text))
            await queue.put(None)

        assert proc.stdout is not None and proc.stderr is not None
        tasks = [
            asyncio.create_task(pump(proc.stdout, "stdout")),
            asyncio.create_task(pump(proc.stderr, "stderr")),
        ]
        finished = 0
        while finished < len(tasks):
            item = await queue.get()
            if item is None:
                finished += 1
                continue
            yield item
        await proc.wait()
        await asyncio.gather(*tasks)

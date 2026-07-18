"""Autonomous agent: a ReAct-style loop that uses tools until the task is done.

Unlike the executor (which applies a fixed batch of actions exactly once), this
agent *iterates*: it asks the model for the next action, runs it through the
tool registry, feeds the observation back, and repeats — enabling multi-file
edits and self-correction. The loop is bounded by a step budget and stops early
if the model declares completion or repeats itself without progress.

Actions use a portable JSON protocol (not vendor-specific function calling), so
every provider — local or hosted — can drive the loop identically.
"""

from __future__ import annotations

import json

from aurora.app.agents.base import BaseAgent
from aurora.app.agents.llm import complete, strip_code_fences, system, user
from aurora.app.agents.models import AgentStep, AutonomousInput, AutonomousReport
from aurora.app.core.logging import get_logger
from aurora.app.core.types import Message, Role
from aurora.app.providers.interface import LLMProvider
from aurora.app.tools.models import ToolResult
from aurora.app.tools.registry import ToolRegistry

_logger = get_logger("agents.autonomous")

_MAX_OBSERVATION = 4000  # cap tool output fed back into the model
_STALL_LIMIT = 2  # identical consecutive actions before giving up

_SYSTEM = (
    "You are AURORA, an autonomous software engineer. Accomplish the user's "
    "task by using tools one step at a time: think, act, observe, repeat.\n\n"
    "Reply with EXACTLY ONE JSON object per step and nothing else — either\n"
    '  {"thought": "...", "tool": "<tool_name>", "args": {...}}\n'
    "to call a tool, or\n"
    '  {"thought": "...", "done": true, "answer": "<what you did>"}\n'
    "when the task is fully complete.\n\n"
    "Rules: change files only via write_file; read before you edit; verify with "
    "run_tests when relevant; take small, safe steps; use only the listed "
    "tools with their exact argument names.\n\n"
    "Available tools:\n"
)


class AutonomousAgent(BaseAgent[AutonomousInput, AutonomousReport]):
    """Iteratively call tools until the task is done or the budget is spent."""

    name = "autonomous"

    def __init__(self, provider: LLMProvider, model: str, tools: ToolRegistry) -> None:
        self._provider = provider
        self._model = model
        self._tools = tools

    async def run(self, request: AutonomousInput) -> AutonomousReport:
        transcript: list[Message] = [
            system(_SYSTEM + self._tool_catalog()),
            *request.context_messages,
            user(f"Task: {request.task}"),
        ]
        steps: list[AgentStep] = []
        last_signature: str | None = None
        stall = 0

        for index in range(1, request.max_steps + 1):
            text = await complete(
                self._provider, self._model, transcript, max_tokens=1200
            )
            transcript.append(Message(role=Role.ASSISTANT, content=text))
            action = self._parse(text)

            if action is None:
                steps.append(
                    AgentStep(index=index, observation="invalid action (not JSON)")
                )
                transcript.append(
                    user("That was not valid JSON. Reply with one JSON object.")
                )
                continue

            if action.get("done"):
                answer = str(action.get("answer", "")).strip() or "Task complete."
                steps.append(
                    AgentStep(
                        index=index,
                        thought=str(action.get("thought", "")),
                        observation="done",
                    )
                )
                return AutonomousReport(answer=answer, completed=True, steps=steps)

            tool = str(action.get("tool", "")).strip()
            args = action.get("args")
            args = args if isinstance(args, dict) else {}
            thought = str(action.get("thought", ""))

            if tool not in self._tools.names():
                observation = (
                    f"unknown tool '{tool}'. Available: "
                    f"{', '.join(self._tools.names())}"
                )
                steps.append(
                    AgentStep(
                        index=index,
                        thought=thought,
                        tool=tool,
                        args=args,
                        ok=False,
                        observation=observation,
                    )
                )
                transcript.append(user(f"Observation: {observation}"))
                continue

            signature = f"{tool}:{json.dumps(args, sort_keys=True)}"
            stall = stall + 1 if signature == last_signature else 0
            last_signature = signature
            if stall >= _STALL_LIMIT:
                steps.append(
                    AgentStep(
                        index=index,
                        thought=thought,
                        tool=tool,
                        args=args,
                        ok=False,
                        observation="stopped: repeated the same action",
                    )
                )
                return AutonomousReport(
                    answer="Stopped: the agent repeated an action without progress.",
                    completed=False,
                    steps=steps,
                )

            result = await self._tools.invoke(tool, args)
            observation = self._observation(result)
            steps.append(
                AgentStep(
                    index=index,
                    thought=thought,
                    tool=tool,
                    args=args,
                    ok=result.ok,
                    observation=observation,
                )
            )
            transcript.append(
                user(f"Observation ({tool}, ok={result.ok}): {observation}")
            )

        _logger.info("autonomous_budget_exhausted", extra={"steps": len(steps)})
        return AutonomousReport(
            answer="Reached the step limit before completing the task.",
            completed=False,
            steps=steps,
        )

    def _tool_catalog(self) -> str:
        """Compact, model-facing description of every available tool."""
        lines = []
        for spec in self._tools.specs():
            schema = spec.get("input_schema", {})
            props = schema.get("properties", {})
            required = set(schema.get("required", []))
            args = ", ".join(f"{k}{'*' if k in required else ''}" for k in props)
            lines.append(f"- {spec['name']}({args}): {spec['description']}")
        return "\n".join(lines)

    @staticmethod
    def _parse(text: str) -> dict | None:
        """Extract the step's JSON object, tolerating fences and stray prose."""
        candidate = strip_code_fences(text).strip()
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass
        # Fallback: the outermost braces (json handles nested braces/strings).
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(candidate[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def _observation(result: ToolResult) -> str:
        payload = result.data if result.ok else result.error
        text = json.dumps(payload, ensure_ascii=False) if payload is not None else ""
        if len(text) > _MAX_OBSERVATION:
            text = text[:_MAX_OBSERVATION] + "…(truncated)"
        return text

"""Autonomous agent: a ReAct-style loop that uses tools until the task is done.

Unlike the executor (which applies a fixed batch of actions exactly once), this
agent *iterates*: it asks the model for the next action(s), runs them through the
tool registry, feeds the observations back, and repeats — enabling multi-file
edits and self-correction. The loop is bounded by a step budget and stops early
if the model declares completion or spins without progress.

The loop is a disciplined engineering state machine, not a naive think→act→
observe: each step declares its **phase** (ANALYZE → PLAN → INVESTIGATE →
EXECUTE → VERIFY → REFLECT → COMPLETE), and completion carries a self-assessment
(:class:`VerificationMetadata`: confidence, what was verified vs assumed, risks,
unknowns). A single step may request several tools at once, executed
concurrently. Actions use a portable JSON protocol (not vendor function
calling), so every provider drives the loop identically.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict

from aurora.app.agents.base import BaseAgent
from aurora.app.agents.llm import complete, lead_system, strip_code_fences, user
from aurora.app.agents.models import (
    AgentPhase,
    AgentStep,
    AutonomousInput,
    AutonomousReport,
    ToolCall,
    VerificationMetadata,
)
from aurora.app.core.logging import get_logger
from aurora.app.core.types import Message, Role
from aurora.app.guards.completion_gate import check_completion
from aurora.app.guards.evidence import build_evidence
from aurora.app.guards.hallucination_guard import assess
from aurora.app.providers.interface import LLMProvider
from aurora.app.tools.models import ToolResult
from aurora.app.tools.registry import ToolRegistry

_logger = get_logger("agents.autonomous")

_MAX_OBSERVATION = 4000  # cap tool output fed back into the model
_STALL_LIMIT = 2  # identical consecutive steps before giving up
_REPEAT_LIMIT = 3  # identical steps anywhere in the run before giving up
_GATE_LIMIT = 2  # rejected completions before giving up (returns INCOMPLETE)
_PHASE_VALUES = frozenset(phase.value for phase in AgentPhase)

_SYSTEM = (
    "You are AURORA's autonomous engineer. Work in a disciplined loop, one step "
    "at a time: think, act, observe, repeat.\n\n"
    "Move through these phases: ANALYZE (understand the objective), PLAN (decide "
    "the strategy), INVESTIGATE (read files/run read-only tools to gather "
    "evidence), EXECUTE (make changes), VERIFY (run tests/checks), REFLECT (look "
    "for mistakes), COMPLETE (only after verifying).\n\n"
    "Reply with EXACTLY ONE JSON object per step and nothing else — either\n"
    '  {"phase": "<PHASE>", "thought": "...", "tool": "<name>", "args": {...}}\n'
    "to call one tool, or\n"
    '  {"phase": "<PHASE>", "thought": "...", "actions": [{"tool": "<t>", '
    '"args": {...}}, ...]}\n'
    "to call several INDEPENDENT tools at once (run in parallel), or\n"
    '  {"phase": "COMPLETE", "thought": "...", "done": true, "answer": "...", '
    '"confidence": 0-100, "verified": [...], "assumptions": [...], "risks": '
    '[...], "unknowns": [...]}\n'
    "when the task is fully complete.\n\n"
    "Verification rules:\n"
    "- Before acting, understand the objective and inspect the current state; do "
    "not act on unverified assumptions.\n"
    "- Before modifying a file, read it first and understand its dependencies "
    "and the impact of the change.\n"
    "- After modifying, validate (e.g. run_tests), inspect errors, and retry on "
    "failure; confirm the final state before declaring done.\n"
    "- Never blindly overwrite files, never assume a command succeeded without "
    "checking, never create duplicate implementations, never skip validation.\n"
    "- Only batch tools that are independent; never write the same file twice in "
    "one batch. Use only the listed tools with their exact argument names.\n\n"
    "Available tools:\n"
)


class AutonomousAgent(BaseAgent[AutonomousInput, AutonomousReport]):
    """Iteratively call tools (singly or in parallel) until done or bounded."""

    name = "autonomous"

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        tools: ToolRegistry,
        system_prompt: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._tools = tools
        self._system_prompt = system_prompt

    async def run(self, request: AutonomousInput) -> AutonomousReport:
        transcript: list[Message] = [
            lead_system(self._system_prompt, _SYSTEM + self._tool_catalog()),
            *request.context_messages,
            user(f"Task: {request.task}"),
        ]
        steps: list[AgentStep] = []
        counts: dict[str, int] = defaultdict(int)
        last_signature: str | None = None
        stall = 0
        gate_rejections = 0
        task_id = request.task[:40]

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

            phase = self._phase(action)
            thought = str(action.get("thought", ""))

            if action.get("done"):
                answer = str(action.get("answer", "")).strip() or "Task complete."
                metadata = self._metadata(action)
                evidence = build_evidence(task_id, steps, metadata)
                completion = check_completion(evidence, assess(answer, evidence))
                # Enforcement: don't accept completion that isn't backed by
                # evidence. Send the reasons back and keep working, up to a cap.
                if not completion.passed and gate_rejections < _GATE_LIMIT:
                    gate_rejections += 1
                    reasons = "; ".join(completion.reasons) or "insufficient evidence"
                    steps.append(
                        AgentStep(
                            index=index,
                            phase=phase or AgentPhase.REFLECT.value,
                            thought=thought,
                            observation=f"completion rejected: {reasons}",
                        )
                    )
                    transcript.append(
                        user(
                            f"Not done yet — {reasons}. Address these with tools, "
                            "then finish."
                        )
                    )
                    continue
                steps.append(
                    AgentStep(
                        index=index,
                        phase=phase or AgentPhase.COMPLETE.value,
                        thought=thought,
                        observation="done" if completion.passed else "incomplete",
                    )
                )
                return AutonomousReport(
                    answer=answer,
                    completed=completion.passed,
                    steps=steps,
                    metadata=metadata,
                    evidence=evidence,
                    completion=completion,
                )

            calls = self._extract_calls(action)
            if not calls:
                steps.append(
                    AgentStep(
                        index=index,
                        phase=phase,
                        thought=thought,
                        observation="no tool or actions specified",
                    )
                )
                transcript.append(
                    user('Specify a "tool", an "actions" list, or "done": true.')
                )
                continue

            signature = self._signature(calls)
            counts[signature] += 1
            stall = stall + 1 if signature == last_signature else 0
            last_signature = signature
            if stall >= _STALL_LIMIT or counts[signature] >= _REPEAT_LIMIT:
                steps.append(
                    AgentStep(
                        index=index,
                        phase=phase,
                        thought=thought,
                        observation="stopped: repeated an action without progress",
                    )
                )
                return AutonomousReport(
                    answer="Stopped: the agent repeated an action without progress.",
                    completed=False,
                    steps=steps,
                )

            results = await self._run_calls(calls)
            steps.append(self._step(index, phase, thought, results))
            transcript.append(user(self._observation_block(results)))

        _logger.info("autonomous_budget_exhausted", extra={"steps": len(steps)})
        return AutonomousReport(
            answer="Reached the step limit before completing the task.",
            completed=False,
            steps=steps,
        )

    async def _run_calls(self, calls: list[tuple[str, dict]]) -> list[ToolCall]:
        """Execute a batch of tool calls concurrently, preserving order."""

        async def one(tool: str, args: dict) -> ToolCall:
            if tool not in self._tools.names():
                available = ", ".join(self._tools.names())
                return ToolCall(
                    tool=tool,
                    args=args,
                    ok=False,
                    observation=f"unknown tool '{tool}'. Available: {available}",
                )
            result = await self._tools.invoke(tool, args)
            return ToolCall(
                tool=tool, args=args, ok=result.ok, observation=self._observation(result)
            )

        return list(await asyncio.gather(*(one(tool, args) for tool, args in calls)))

    @staticmethod
    def _step(index: int, phase: str, thought: str, results: list[ToolCall]) -> AgentStep:
        """Build a step, mirroring the single call into the scalar fields."""
        if len(results) == 1:
            call = results[0]
            return AgentStep(
                index=index,
                phase=phase,
                thought=thought,
                tool=call.tool,
                args=call.args,
                ok=call.ok,
                observation=call.observation,
                calls=results,
            )
        return AgentStep(
            index=index,
            phase=phase,
            thought=thought,
            ok=all(bool(call.ok) for call in results),
            observation="; ".join(f"{c.tool}: ok={c.ok}" for c in results),
            calls=results,
        )

    @staticmethod
    def _observation_block(results: list[ToolCall]) -> str:
        """Format the observation(s) fed back into the transcript."""
        if len(results) == 1:
            call = results[0]
            return f"Observation ({call.tool}, ok={call.ok}): {call.observation}"
        lines = [f"[{c.tool} ok={c.ok}] {c.observation}" for c in results]
        return "Observations:\n" + "\n".join(lines)

    @staticmethod
    def _extract_calls(action: dict) -> list[tuple[str, dict]]:
        """Normalize the action into an ordered list of (tool, args) calls."""
        raw = action.get("actions")
        if isinstance(raw, list):
            calls: list[tuple[str, dict]] = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                tool = str(item.get("tool", "")).strip()
                args = item.get("args")
                if tool:
                    calls.append((tool, args if isinstance(args, dict) else {}))
            return calls
        tool = str(action.get("tool", "")).strip()
        if not tool:
            return []
        args = action.get("args")
        return [(tool, args if isinstance(args, dict) else {})]

    @staticmethod
    def _signature(calls: list[tuple[str, dict]]) -> str:
        """A batch-order-independent signature for loop detection."""
        parts = sorted(
            f"{tool}:{json.dumps(args, sort_keys=True)}" for tool, args in calls
        )
        return " | ".join(parts)

    @staticmethod
    def _phase(action: dict) -> str:
        """Read a valid engineering phase from the action, or '' if absent."""
        raw = str(action.get("phase", "")).strip().upper()
        return raw if raw in _PHASE_VALUES else ""

    @staticmethod
    def _metadata(action: dict) -> VerificationMetadata:
        """Parse the completion self-assessment, tolerating missing fields."""

        def strings(key: str) -> list[str]:
            value = action.get(key)
            return [str(item) for item in value] if isinstance(value, list) else []

        raw = action.get("confidence")
        confidence = int(raw) if isinstance(raw, (int, float)) and 0 <= raw <= 100 else 0
        return VerificationMetadata(
            confidence=confidence,
            verified=strings("verified"),
            assumptions=strings("assumptions"),
            risks=strings("risks"),
            unknowns=strings("unknowns"),
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

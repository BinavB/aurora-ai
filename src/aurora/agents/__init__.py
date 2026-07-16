"""Agents layer: orchestration over providers, memory, and tools.

An agent composes lower layers into a coherent behaviour. The built-in
:class:`~aurora.agents.chat.ChatAgent` runs multi-turn conversations, persisting
history through a :class:`~aurora.memory.base.BaseMemory`.
"""

from aurora.agents.base import BaseAgent
from aurora.agents.chat import ChatAgent

__all__ = ["BaseAgent", "ChatAgent"]

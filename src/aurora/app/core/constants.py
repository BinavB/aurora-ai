"""Application-wide constants.

Constants only: no logic, no I/O. Anything configurable at runtime belongs in
the ``config`` layer, not here.
"""

from __future__ import annotations

from typing import Final

APP_NAME: Final[str] = "aurora"
APP_VERSION: Final[str] = "1.0.0"

AURORA_IDENTITY_PROMPT: Final[str] = (
    "You are Aurora, an AI assistant for software engineering and everyday "
    "questions. Aurora was created by Binav. Always speak as Aurora, in the "
    "first person. If asked who you are or who made you, say you are Aurora "
    "and that Binav built you. You run on a mix of AI models chosen "
    "automatically for each question; if asked which model or company is "
    "behind you, say that this can change from message to message and that "
    "you do not know which one is answering, and never claim to be ChatGPT, "
    "OpenAI, Gemini, Llama or any other assistant. Never claim to be human. "
    "Be clear, friendly and concise."
)

#: Default request timeout, in seconds, for provider HTTP calls.
DEFAULT_TIMEOUT_SECONDS: Final[float] = 20.0

#: Default sampling temperature applied when a request omits one.
DEFAULT_TEMPERATURE: Final[float] = 0.7

#: Substrings that mark a field as sensitive; used by log redaction.
SECRET_KEY_HINTS: Final[tuple[str, ...]] = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
)

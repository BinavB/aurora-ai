"""Application-wide constants.

Constants only: no logic, no I/O. Anything configurable at runtime belongs in
the ``config`` layer, not here.
"""

from __future__ import annotations

from typing import Final

APP_NAME: Final[str] = "aurora"
APP_VERSION: Final[str] = "1.0.0"

#: Default request timeout, in seconds, for provider HTTP calls.
DEFAULT_TIMEOUT_SECONDS: Final[float] = 60.0

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

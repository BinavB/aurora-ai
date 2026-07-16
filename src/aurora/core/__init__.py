"""Core layer: shared types, configuration, and errors.

This layer has no dependencies on any other AURORA layer. Every other layer
may depend on ``core``; ``core`` depends on nothing internal.
"""

from aurora.core.config import ProviderConfig, Settings
from aurora.core.errors import (
    AuroraError,
    ConfigurationError,
    ProviderError,
    ProviderRequestError,
    ProviderResponseError,
)
from aurora.core.types import (
    ChatRequest,
    ChatResponse,
    Message,
    Role,
    Usage,
)

__all__ = [
    "ProviderConfig",
    "Settings",
    "AuroraError",
    "ConfigurationError",
    "ProviderError",
    "ProviderRequestError",
    "ProviderResponseError",
    "ChatRequest",
    "ChatResponse",
    "Message",
    "Role",
    "Usage",
]

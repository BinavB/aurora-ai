"""Core layer: shared utilities depended upon by every other layer.

Provides constants, the exception hierarchy, structured logging, the event
bus, the dependency-injection container, and shared domain types. Contains no
business logic and depends on no other AURORA layer.
"""

from aurora.app.core.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
)
from aurora.app.core.container import Container
from aurora.app.core.events import Event, EventBus
from aurora.app.core.exceptions import (
    AuroraError,
    ConfigurationError,
    ConfirmationRequiredError,
    PermissionDeniedError,
    ProviderError,
    ProviderRequestError,
    ProviderResponseError,
    RegistryError,
    RouterError,
    ToolError,
    TranscriptionError,
    ValidationError,
)
from aurora.app.core.logging import configure_logging, get_logger, redact
from aurora.app.core.types import ChatRequest, ChatResponse, Message, Role, Usage

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT_SECONDS",
    "Container",
    "Event",
    "EventBus",
    "AuroraError",
    "ConfigurationError",
    "ConfirmationRequiredError",
    "PermissionDeniedError",
    "ProviderError",
    "ProviderRequestError",
    "ProviderResponseError",
    "RegistryError",
    "RouterError",
    "ToolError",
    "TranscriptionError",
    "ValidationError",
    "configure_logging",
    "get_logger",
    "redact",
    "ChatRequest",
    "ChatResponse",
    "Message",
    "Role",
    "Usage",
]

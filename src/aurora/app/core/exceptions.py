"""Structured exception hierarchy shared across all layers.

Every AURORA error derives from :class:`AuroraError` and carries a machine
readable ``code`` plus an optional ``details`` mapping, so failures can be
serialized into structured API responses without leaking stack traces.
"""

from __future__ import annotations

from typing import Any


class AuroraError(Exception):
    """Base class for every error raised by AURORA.

    Attributes:
        message: Human-readable description of the failure.
        code: Stable, machine-readable error code.
        details: Optional structured context (never secrets).
    """

    code: str = "aurora_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details: dict[str, Any] = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the error."""
        return {"code": self.code, "message": self.message, "details": self.details}


class ConfigurationError(AuroraError):
    """Raised when configuration is missing or invalid."""

    code = "configuration_error"


class ValidationError(AuroraError):
    """Raised when input fails validation."""

    code = "validation_error"


class ProviderError(AuroraError):
    """Base class for provider-related failures."""

    code = "provider_error"


class ProviderRequestError(ProviderError):
    """Raised when a provider request cannot be completed (transport/HTTP)."""

    code = "provider_request_error"


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an uninterpretable response."""

    code = "provider_response_error"


class RegistryError(AuroraError):
    """Raised when a requested item is absent from a registry."""

    code = "registry_error"


class ToolError(AuroraError):
    """Base class for tool execution failures."""

    code = "tool_error"


class RouterError(AuroraError):
    """Raised when the router cannot select a provider/model."""

    code = "router_error"


class TranscriptionError(AuroraError):
    """Raised when audio transcription fails."""

    code = "transcription_error"


class PermissionDeniedError(ToolError):
    """Raised when a tool is invoked without the required permissions."""

    code = "permission_denied"


class ConfirmationRequiredError(ToolError):
    """Raised when a dangerous action is attempted without confirmation."""

    code = "confirmation_required"

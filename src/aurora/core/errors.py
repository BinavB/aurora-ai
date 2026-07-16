"""Exception hierarchy shared across all AURORA layers."""

from __future__ import annotations


class AuroraError(Exception):
    """Base class for every error raised by AURORA."""


class ConfigurationError(AuroraError):
    """Raised when configuration is missing or invalid."""


class ProviderError(AuroraError):
    """Base class for provider-related failures."""


class ProviderRequestError(ProviderError):
    """Raised when a provider request cannot be completed (transport/HTTP)."""


class ProviderResponseError(ProviderError):
    """Raised when a provider returns a response AURORA cannot interpret."""

"""Validated configuration models.

Configuration is explicit and typed. Models here hold no I/O; loading from the
environment lives in :mod:`aurora.app.config.loader`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aurora.app.core.constants import DEFAULT_TIMEOUT_SECONDS
from aurora.app.core.exceptions import ConfigurationError


class ProviderSettings(BaseModel):
    """Connection settings for a single LLM provider.

    Attributes:
        base_url: Root URL of the provider API.
        api_key: Secret credential, if the provider requires one.
        timeout: Per-request timeout in seconds.
    """

    base_url: str = Field(min_length=1)
    api_key: str | None = None
    timeout: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0.0)


class AppSettings(BaseModel):
    """Top-level application settings.

    Attributes:
        log_level: Logging level name (e.g. ``INFO``).
        providers: Provider settings keyed by provider name.
    """

    log_level: str = "INFO"
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)

    def provider(self, name: str) -> ProviderSettings:
        """Return settings for ``name``.

        Raises:
            ConfigurationError: If the provider is not configured.
        """
        try:
            return self.providers[name]
        except KeyError as exc:
            raise ConfigurationError(
                f"No configuration for provider '{name}'",
                details={"provider": name},
            ) from exc

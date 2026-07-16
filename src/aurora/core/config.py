"""Configuration models.

Configuration is explicit and validated. Values may be supplied directly or
loaded from environment variables via :meth:`Settings.from_env`.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from aurora.core.errors import ConfigurationError


class ProviderConfig(BaseModel):
    """Connection settings for a single provider."""

    base_url: str
    api_key: str | None = None
    timeout: float = Field(default=60.0, gt=0.0)


# Default endpoints and the environment variable holding each provider's key.
_PROVIDER_DEFAULTS: dict[str, tuple[str, str | None]] = {
    "ollama": ("http://localhost:11434", None),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "anthropic": ("https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY"),
}


class Settings(BaseModel):
    """Top-level platform settings keyed by provider name."""

    providers: dict[str, ProviderConfig] = Field(default_factory=dict)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        """Build settings from environment variables.

        ``AURORA_<PROVIDER>_BASE_URL`` overrides the default endpoint; the
        provider's key variable (e.g. ``OPENAI_API_KEY``) supplies the key.
        """
        source = os.environ if env is None else env
        providers: dict[str, ProviderConfig] = {}
        for name, (default_url, key_var) in _PROVIDER_DEFAULTS.items():
            base_url = source.get(f"AURORA_{name.upper()}_BASE_URL", default_url)
            api_key = source.get(key_var) if key_var else None
            providers[name] = ProviderConfig(base_url=base_url, api_key=api_key)
        return cls(providers=providers)

    def require(self, name: str) -> ProviderConfig:
        """Return the config for ``name`` or raise if it is absent."""
        try:
            return self.providers[name]
        except KeyError as exc:
            raise ConfigurationError(f"No configuration for provider '{name}'") from exc

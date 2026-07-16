"""Load application settings from the environment.

Endpoints default to each provider's public API; ``AURORA_<PROVIDER>_BASE_URL``
overrides an endpoint and the provider's documented key variable supplies the
credential. Keys are read but never logged.
"""

from __future__ import annotations

import os
from typing import Final

from aurora.app.config.models import AppSettings, ProviderSettings

# provider -> (default base url, environment variable holding the api key)
_PROVIDER_DEFAULTS: Final[dict[str, tuple[str, str | None]]] = {
    "ollama": ("http://localhost:11434", None),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "anthropic": ("https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY"),
}


def load_settings(env: dict[str, str] | None = None) -> AppSettings:
    """Build :class:`AppSettings` from environment variables.

    Args:
        env: Environment mapping to read; defaults to ``os.environ``.

    Returns:
        Fully populated application settings.
    """
    source = os.environ if env is None else env
    providers: dict[str, ProviderSettings] = {}
    for name, (default_url, key_var) in _PROVIDER_DEFAULTS.items():
        providers[name] = ProviderSettings(
            base_url=source.get(f"AURORA_{name.upper()}_BASE_URL", default_url),
            api_key=source.get(key_var) if key_var else None,
        )
    return AppSettings(
        log_level=source.get("AURORA_LOG_LEVEL", "INFO"),
        providers=providers,
    )

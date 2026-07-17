"""Load application settings from the environment.

Endpoints default to each provider's public API; ``AURORA_<PROVIDER>_BASE_URL``
overrides an endpoint and the provider's documented key variable supplies the
credential. Keys are read but never logged.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from aurora.app.config.models import AppSettings, ProviderSettings


def read_dotenv(path: str | Path) -> dict[str, str]:
    """Parse a ``.env`` file into a mapping (``KEY=value`` lines).

    Blank lines and ``#`` comments are ignored; surrounding quotes are
    stripped. Missing files yield an empty mapping.
    """
    result: dict[str, str] = {}
    file = Path(path)
    if not file.is_file():
        return result
    for line in file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


# provider -> (default base url, environment variable holding the api key)
_PROVIDER_DEFAULTS: Final[dict[str, tuple[str, str | None]]] = {
    "ollama": ("http://localhost:11434", None),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "anthropic": ("https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
}


def load_settings(
    env: dict[str, str] | None = None, dotenv_path: str | Path | None = None
) -> AppSettings:
    """Build :class:`AppSettings` from environment variables and an optional .env.

    Args:
        env: Environment mapping to read; defaults to ``os.environ``.
        dotenv_path: Path to a ``.env`` file whose values fill any gaps not
            already set in the environment. Defaults to ``AURORA_ENV_FILE`` or
            ``./.env`` when ``env`` is not supplied.

    Returns:
        Fully populated application settings.
    """
    if env is None:
        path = dotenv_path or os.environ.get("AURORA_ENV_FILE", ".env")
        # Real environment variables take precedence over the .env file.
        source: dict[str, str] = {**read_dotenv(path), **os.environ}
    else:
        source = dict(env)
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

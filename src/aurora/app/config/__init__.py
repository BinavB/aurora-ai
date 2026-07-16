"""Config layer: typed settings and environment loading.

Depends only on ``core``. Provides validated settings models and a loader that
reads them from the environment without exposing secrets.
"""

from aurora.app.config.loader import load_settings
from aurora.app.config.models import AppSettings, ProviderSettings

__all__ = ["load_settings", "AppSettings", "ProviderSettings"]

"""Router layer: choose provider, model, tools, and context.

Pure policy over model metadata; contains no provider-specific code. Depends on
``config`` (for availability) and ``core`` only.
"""

from aurora.app.router.catalog import ModelCatalog, build_catalog
from aurora.app.router.models import (
    Capability,
    ModelProfile,
    RoutingDecision,
    RoutingRequest,
)
from aurora.app.router.router import Router

__all__ = [
    "ModelCatalog",
    "build_catalog",
    "Capability",
    "ModelProfile",
    "RoutingDecision",
    "RoutingRequest",
    "Router",
]

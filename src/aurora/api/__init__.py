"""API layer: an HTTP surface over the platform.

:func:`create_app` wires the lower layers into a FastAPI application. It takes
its collaborators as arguments so tests can inject fakes and deployments can
supply real settings.
"""

from aurora.api.app import create_app

__all__ = ["create_app"]

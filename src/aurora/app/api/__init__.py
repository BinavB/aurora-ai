"""API layer: the FastAPI orchestration surface.

Thin endpoints (REST, SSE streaming, WebSocket) delegate to the services layer.
No business logic lives here.
"""

from aurora.app.api.app import create_app

__all__ = ["create_app"]

"""Web tools: the sanctioned path for outbound HTTP reads (SSRF-guarded)."""

from aurora.app.tools.registry import ToolRegistry
from aurora.app.tools.web.tools import ClientFactory, FetchUrlTool


def web_registry(client_factory: ClientFactory | None = None) -> ToolRegistry:
    """Build a registry of the web tools.

    Args:
        client_factory: Optional zero-arg factory returning an ``httpx``
            client (a test/transport seam). When provided, DNS SSRF checks are
            skipped because the transport is trusted.
    """
    return ToolRegistry([FetchUrlTool(client_factory)])


__all__ = ["FetchUrlTool", "web_registry"]

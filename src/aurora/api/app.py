"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from aurora.agents.chat import ChatAgent
from aurora.core.config import ProviderConfig, Settings
from aurora.core.errors import AuroraError
from aurora.memory.base import BaseMemory
from aurora.memory.in_memory import InMemoryMemory
from aurora.providers.base import BaseProvider
from aurora.providers.registry import build_provider, registered_providers
from aurora.tools.registry import ToolRegistry

_FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "index.html"

# A provider factory lets tests inject fakes; production uses the registry.
ProviderFactory = Callable[[str, ProviderConfig], BaseProvider]


class ChatBody(BaseModel):
    session_id: str = Field(min_length=1)
    provider: str
    model: str
    message: str = Field(min_length=1)
    system: str | None = None


class ToolBody(BaseModel):
    arguments: dict[str, object] = Field(default_factory=dict)


def create_app(
    settings: Settings | None = None,
    memory: BaseMemory | None = None,
    tools: ToolRegistry | None = None,
    provider_factory: ProviderFactory | None = None,
) -> FastAPI:
    """Build the AURORA API application from its collaborators."""
    settings = settings or Settings.from_env()
    memory = memory or InMemoryMemory()
    tools = tools if tools is not None else ToolRegistry()
    make_provider = provider_factory or (
        lambda name, config: build_provider(name, config)
    )

    app = FastAPI(title="AURORA AI", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/providers")
    async def providers() -> dict[str, list[str]]:
        return {"providers": list(registered_providers())}

    @app.get("/tools")
    async def list_tools() -> dict[str, list[dict[str, object]]]:
        return {"tools": tools.specs()}

    @app.post("/tools/{name}")
    async def run_tool(name: str, body: ToolBody) -> dict[str, object]:
        try:
            result = await tools.invoke(name, **body.arguments)
        except AuroraError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return result.model_dump()

    @app.post("/chat")
    async def chat(body: ChatBody) -> dict[str, object]:
        try:
            config = settings.require(body.provider)
            provider = make_provider(body.provider, config)
        except AuroraError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        agent = ChatAgent(
            provider=provider,
            memory=memory,
            model=body.model,
            system_prompt=body.system,
        )
        try:
            response = await agent.run(body.session_id, body.message)
        except AuroraError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        finally:
            await provider.aclose()
        return response.model_dump()

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        if _FRONTEND.exists():
            return _FRONTEND.read_text(encoding="utf-8")
        return "<h1>AURORA AI</h1>"

    return app

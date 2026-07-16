"""FastAPI application factory.

Endpoints are thin: they validate input, call a service, and return the result.
All coordination lives in the services layer; the API only orchestrates.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse

from aurora.app.api.errors import install_error_handlers
from aurora.app.api.schemas import ChatBody, ImplementBody, PlanBody, ReviewBody
from aurora.app.config.loader import load_settings
from aurora.app.config.models import AppSettings
from aurora.app.core.events import EventBus
from aurora.app.core.exceptions import AuroraError
from aurora.app.core.logging import configure_logging, get_logger
from aurora.app.database.engine import Database
from aurora.app.memory.store import MemoryStore
from aurora.app.providers.registry import registered_providers
from aurora.app.router.catalog import build_catalog
from aurora.app.router.router import Router
from aurora.app.services.chat_service import ChatService
from aurora.app.services.factory import DefaultProviderFactory, ProviderFactory
from aurora.app.services.implementation_service import ImplementationService
from aurora.app.services.models import (
    ChatReply,
    ImplementResult,
    PlanResult,
    ReviewOutcome,
)
from aurora.app.services.planning_service import PlanningService
from aurora.app.services.review_service import ReviewService
from aurora.app.services.transcription_service import TranscriptionService
from aurora.app.tools.filesystem import filesystem_registry
from aurora.app.tools.terminal import terminal_registry

_logger = get_logger("api.app")


def create_app(
    *,
    settings: AppSettings | None = None,
    memory: MemoryStore | None = None,
    router: Router | None = None,
    factory: ProviderFactory | None = None,
    workspace_root: str | None = None,
    system_prompt: str | None = None,
    frontend_dir: str | None = None,
    transcription: TranscriptionService | None = None,
) -> FastAPI:
    """Build the AURORA API from its collaborators (all injectable)."""
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    events = EventBus()
    memory = memory or MemoryStore(Database(os.environ.get("AURORA_DB_PATH", ":memory:")))
    router = router or Router(build_catalog(settings))
    factory = factory or DefaultProviderFactory(settings, events)
    workspace_root = workspace_root or os.getcwd()

    chat = ChatService(router, factory, memory, system_prompt)
    planning = PlanningService(router, factory)
    review = ReviewService(router, factory)
    implementation = ImplementationService(router, factory)
    transcription = transcription or TranscriptionService()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await memory.open()
        _logger.info("api_started")
        yield
        await memory.close()

    app = FastAPI(title="AURORA AI", version="1.0.0", lifespan=lifespan)
    install_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/providers")
    async def providers() -> dict[str, list[str]]:
        return {"providers": list(registered_providers())}

    @app.get("/tools")
    async def tools() -> dict[str, list]:
        specs = filesystem_registry(workspace_root).specs()
        specs += terminal_registry(workspace_root).specs()
        return {"tools": specs}

    @app.post("/chat")
    async def post_chat(body: ChatBody) -> ChatReply:
        return await chat.chat(
            body.session_id,
            body.message,
            offline=body.offline,
            prefer_provider=body.prefer_provider,
            prefer_model=body.prefer_model,
        )

    @app.post("/chat/stream")
    async def post_chat_stream(body: ChatBody) -> StreamingResponse:
        reply = await chat.chat(
            body.session_id,
            body.message,
            offline=body.offline,
            prefer_provider=body.prefer_provider,
            prefer_model=body.prefer_model,
        )
        return StreamingResponse(_sse(reply.content), media_type="text/event-stream")

    @app.post("/plan")
    async def post_plan(body: PlanBody) -> PlanResult:
        return await planning.plan(
            body.task,
            workspace_root,
            offline=body.offline,
            prefer_provider=body.prefer_provider,
            prefer_model=body.prefer_model,
        )

    @app.post("/review")
    async def post_review(body: ReviewBody) -> ReviewOutcome:
        return await review.review(
            body.code,
            focus=body.focus,
            offline=body.offline,
            prefer_provider=body.prefer_provider,
            prefer_model=body.prefer_model,
        )

    @app.post("/implement")
    async def post_implement(body: ImplementBody) -> ImplementResult:
        return await implementation.implement(
            body.instruction,
            body.target_path,
            workspace_root,
            approve=body.approve,
            offline=body.offline,
            prefer_provider=body.prefer_provider,
            prefer_model=body.prefer_model,
        )

    @app.post("/transcribe")
    async def transcribe(audio: UploadFile = File(...)) -> dict[str, str]:
        data = await audio.read()
        suffix = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
        return {"text": await transcription.transcribe(data, suffix=suffix)}

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                await _handle_ws_turn(chat, websocket, data)
        except WebSocketDisconnect:
            return

    _mount_frontend(app, frontend_dir)
    return app


async def _handle_ws_turn(chat: ChatService, websocket: WebSocket, data: dict) -> None:
    """Run one WebSocket chat turn, streaming tokens or a structured error."""
    try:
        reply = await chat.chat(
            data["session_id"],
            data["message"],
            offline=data.get("offline", False),
            prefer_provider=data.get("prefer_provider"),
            prefer_model=data.get("prefer_model"),
        )
    except AuroraError as exc:
        await websocket.send_json({"type": "error", **exc.to_dict()})
        return
    for token in reply.content.split():
        await websocket.send_json({"type": "token", "content": token})
    await websocket.send_json(
        {"type": "done", "provider": reply.provider, "model": reply.model}
    )


def _mount_frontend(app: FastAPI, frontend_dir: str | None) -> None:
    """Serve ``frontend_dir/index.html`` at ``/`` when configured."""
    if frontend_dir is None:
        return
    index = Path(frontend_dir) / "index.html"
    if not index.is_file():
        return

    @app.get("/", response_class=HTMLResponse)
    async def index_page() -> str:
        return index.read_text(encoding="utf-8")


async def _sse(content: str) -> AsyncIterator[str]:
    """Yield content as Server-Sent Events, one token per event."""
    for token in content.split():
        yield f"data: {token}\n\n"
    yield "data: [DONE]\n\n"

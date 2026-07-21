"""FastAPI application factory.

Endpoints are thin: they validate input, call a service, and return the result.
All coordination lives in the services layer; the API only orchestrates.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse

from aurora.app.api.errors import install_error_handlers
from aurora.app.api.schemas import (
    AgentBody,
    ChatBody,
    CollaborateBody,
    ImplementBody,
    KeysBody,
    PlanBody,
    ReviewBody,
)
from aurora.app.config.loader import load_settings
from aurora.app.config.models import AppSettings
from aurora.app.core.events import EventBus
from aurora.app.core.exceptions import AuroraError, ValidationError
from aurora.app.core.logging import configure_logging, get_logger
from aurora.app.database.engine import Database
from aurora.app.memory.store import MemoryStore
from aurora.app.providers.registry import registered_providers
from aurora.app.router.catalog import build_catalog
from aurora.app.router.models import Capability, TaskKind
from aurora.app.router.router import Router
from aurora.app.services.autonomous_service import AutonomousService
from aurora.app.services.chat_service import ChatService
from aurora.app.services.collaboration_service import CollaborationService, Effort
from aurora.app.services.factory import DefaultProviderFactory, ProviderFactory
from aurora.app.services.implementation_service import ImplementationService
from aurora.app.services.models import (
    AgentResult,
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
from aurora.app.tools.web import web_registry

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
    enable_agent: bool | None = None,
) -> FastAPI:
    """Build the AURORA API from its collaborators (all injectable)."""
    settings = settings or load_settings()
    if enable_agent is None:
        enable_agent = os.environ.get("AURORA_ENABLE_AGENT", "").lower() in {
            "1",
            "true",
            "yes",
        }
    configure_logging(settings.log_level)
    events = EventBus()
    memory = memory or MemoryStore(Database(os.environ.get("AURORA_DB_PATH", ":memory:")))
    router = router or Router(build_catalog(settings))
    factory = factory or DefaultProviderFactory(settings, events)
    workspace_root = workspace_root or os.getcwd()

    def resolve_workspace(requested: str | None) -> str:
        """Resolve the workspace for a request.

        A client-supplied path is honored only on a trusted backend (where the
        agent is enabled), letting the IDE target its open folder. Elsewhere the
        server's configured workspace is always used, so a hosted deployment can
        never be pointed at an arbitrary directory.
        """
        if not requested or not enable_agent:
            return workspace_root
        if not Path(requested).is_dir():
            raise ValidationError(
                "workspace is not an existing directory",
                details={"workspace": requested},
            )
        return str(Path(requested).resolve())

    chat = ChatService(router, factory, memory, system_prompt)
    planning = PlanningService(router, factory)
    review = ReviewService(router, factory)
    implementation = ImplementationService(router, factory)
    collaboration = CollaborationService(router, factory)
    autonomous = AutonomousService(router, factory)
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
        specs += web_registry().specs()
        return {"tools": specs}

    _AUDIO_PROVIDERS = {"gemini", "groq", "openai"}

    @app.get("/capabilities")
    async def capabilities() -> dict[str, bool]:
        available = build_catalog(settings).available()
        vision = any(Capability.VISION in m.capabilities for m in available)
        has_audio_provider = any(m.provider in _AUDIO_PROVIDERS for m in available)
        audio = transcription.available() and has_audio_provider
        return {"vision": vision, "audio": audio, "agent": enable_agent}

    @app.post("/keys")
    async def set_keys(body: KeysBody) -> dict[str, list[str]]:
        updated = []
        for provider, key in body.keys.items():
            config = settings.providers.get(provider)
            if config is not None and key.strip():
                config.api_key = key.strip()
                updated.append(provider)
        catalog = build_catalog(settings)
        router.reload(catalog)
        available = sorted({m.provider for m in catalog.available()})
        return {"updated": sorted(updated), "available": available}

    @app.post("/chat")
    async def post_chat(body: ChatBody) -> ChatReply:
        return await chat.chat(
            body.session_id,
            body.message,
            offline=body.offline,
            prefer_provider=body.prefer_provider,
            prefer_model=body.prefer_model,
            images=body.images,
        )

    @app.post("/chat/stream")
    async def post_chat_stream(body: ChatBody) -> StreamingResponse:
        return StreamingResponse(_chat_sse(chat, body), media_type="text/event-stream")

    @app.post("/plan")
    async def post_plan(body: PlanBody) -> PlanResult:
        return await planning.plan(
            body.task,
            resolve_workspace(body.workspace),
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
            resolve_workspace(body.workspace),
            approve=body.approve,
            offline=body.offline,
            prefer_provider=body.prefer_provider,
            prefer_model=body.prefer_model,
        )

    _MODE_KIND = {
        "chat": TaskKind.CHAT,
        "plan": TaskKind.PLAN,
        "review": TaskKind.REVIEW,
        "implement": TaskKind.IMPLEMENT,
        "summarize": TaskKind.SUMMARIZE,
        "explain": TaskKind.EXPLAIN,
    }

    @app.post("/collaborate")
    async def collaborate(body: CollaborateBody):
        kind = _MODE_KIND.get(body.mode, TaskKind.CHAT)
        try:
            effort = Effort(body.effort)
        except ValueError:
            effort = Effort.BALANCED
        return await collaboration.collaborate(kind, body.task, effort=effort)

    if enable_agent:

        @app.post("/agent")
        async def run_agent(body: AgentBody) -> AgentResult:
            return await autonomous.run(
                body.task,
                resolve_workspace(body.workspace),
                max_steps=body.max_steps,
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
                await _stream_ws_turn(chat, websocket, data)
        except WebSocketDisconnect:
            return

    _mount_frontend(app, frontend_dir)
    return app


async def _chat_sse(chat: ChatService, body: ChatBody) -> AsyncIterator[str]:
    """Stream a chat turn as Server-Sent Events (one JSON frame per delta)."""
    try:
        async for chunk in chat.stream_chat(
            body.session_id,
            body.message,
            offline=body.offline,
            prefer_provider=body.prefer_provider,
            prefer_model=body.prefer_model,
        ):
            yield f"data: {chunk.model_dump_json()}\n\n"
    except AuroraError as exc:
        yield f"data: {json.dumps({'type': 'error', **exc.to_dict()})}\n\n"
    yield "data: [DONE]\n\n"


async def _stream_ws_turn(chat: ChatService, websocket: WebSocket, data: dict) -> None:
    """Stream one WebSocket chat turn as token frames, or a structured error."""
    try:
        if data.get("images"):
            # Vision turns are not streamed: reply in a single terminal frame.
            reply = await chat.chat(
                data["session_id"],
                data["message"],
                offline=data.get("offline", False),
                prefer_provider=data.get("prefer_provider"),
                prefer_model=data.get("prefer_model"),
                images=data["images"],
            )
            await websocket.send_json(
                {
                    "type": "done",
                    "provider": reply.provider,
                    "model": reply.model,
                    "content": reply.content,
                }
            )
            return
        async for chunk in chat.stream_chat(
            data["session_id"],
            data["message"],
            offline=data.get("offline", False),
            prefer_provider=data.get("prefer_provider"),
            prefer_model=data.get("prefer_model"),
        ):
            await websocket.send_json(chunk.model_dump())
    except AuroraError as exc:
        await websocket.send_json({"type": "error", **exc.to_dict()})


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

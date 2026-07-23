"""Tests for the API layer, driven with FastAPI's TestClient."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aurora.app.api import create_app
from aurora.app.config.models import AppSettings, ProviderSettings
from aurora.app.core.exceptions import ProviderRequestError
from aurora.app.core.types import ChatRequest, ChatResponse
from aurora.app.database import Database
from aurora.app.memory import MemoryStore
from aurora.app.providers.base import BaseProvider
from aurora.app.router import Router, build_catalog
from aurora.app.services.factory import ProviderFactory
from aurora.app.services.transcription_service import TranscriptionService
from tests.app.conftest import EchoProvider, ScriptedProvider


class FailingProvider(BaseProvider):
    """A provider whose chat call always fails at the transport layer."""

    name = "openai"

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        raise ProviderRequestError("simulated outage")


def _settings(**keys: str) -> AppSettings:
    providers = {
        "ollama": ProviderSettings(base_url="http://localhost:11434"),
        "openai": ProviderSettings(base_url="https://api.openai.com/v1"),
        "anthropic": ProviderSettings(base_url="https://api.anthropic.com/v1"),
        "gemini": ProviderSettings(base_url="https://gen.googleapis.com"),
        "xai": ProviderSettings(base_url="https://api.x.ai/v1"),
        "groq": ProviderSettings(base_url="https://api.groq.com/openai/v1"),
        "mistral": ProviderSettings(base_url="https://api.mistral.ai/v1"),
        "openrouter": ProviderSettings(base_url="https://openrouter.ai/api/v1"),
    }
    for name, key in keys.items():
        providers[name] = providers[name].model_copy(update={"api_key": key})
    return AppSettings(providers=providers)


class FakeFactory(ProviderFactory):
    def __init__(self, provider: BaseProvider) -> None:
        self._provider = provider

    def create(self, provider: str) -> BaseProvider:
        return self._provider


def _client(provider: BaseProvider, tmp_path: Path, **keys: str) -> TestClient:
    settings = _settings(**keys)
    app = create_app(
        settings=settings,
        memory=MemoryStore(Database()),
        router=Router(build_catalog(settings)),
        factory=FakeFactory(provider),
        workspace_root=str(tmp_path),
        transcription=TranscriptionService(
            transcriber=lambda audio, suffix: "hello from voice"
        ),
    )
    return TestClient(app)


def _echo() -> EchoProvider:
    return EchoProvider(ProviderSettings(base_url="http://echo.local"))


# --- basics ---------------------------------------------------------------


def test_health_and_providers(tmp_path: Path) -> None:
    with _client(_echo(), tmp_path) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert "anthropic" in client.get("/providers").json()["providers"]


def test_tools_listing(tmp_path: Path) -> None:
    with _client(_echo(), tmp_path) as client:
        names = {t["name"] for t in client.get("/tools").json()["tools"]}
    assert {"read_file", "write_file", "run_terminal"} <= names


# --- chat -----------------------------------------------------------------


def test_chat_endpoint(tmp_path: Path) -> None:
    with _client(_echo(), tmp_path) as client:
        res = client.post("/chat", json={"session_id": "s", "message": "hi"})
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "ollama"
    # 2 messages: the injected AURORA system prompt + the user turn.
    assert body["content"] == "echo[2]: hi"


def test_chat_stream_is_sse(tmp_path: Path) -> None:
    import json

    with _client(_echo(), tmp_path) as client:
        res = client.post("/chat/stream", json={"session_id": "s", "message": "hi there"})
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    assert res.text.strip().endswith("data: [DONE]")
    # The terminal frame is a real JSON chunk carrying provider/model + content.
    frames = [
        json.loads(line[6:])
        for line in res.text.splitlines()
        if line.startswith("data: ") and line[6:] != "[DONE]"
    ]
    done = next(f for f in frames if f["type"] == "done")
    assert done["provider"] == "ollama"
    assert done["content"] == "echo[2]: hi there"


def test_chat_websocket_streams_tokens(tmp_path: Path) -> None:
    with _client(_echo(), tmp_path) as client, client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"session_id": "s", "message": "hi"})
        tokens = []
        while (msg := ws.receive_json())["type"] != "done":
            tokens.append(msg["content"])
        # Real deltas reassemble into the full reply; the done frame carries meta.
        assert "".join(tokens) == "echo[2]: hi"
        assert msg["provider"] == "ollama"
        assert msg["content"] == "echo[2]: hi"


def test_chat_websocket_sends_structured_error_instead_of_crashing(
    tmp_path: Path,
) -> None:
    # A provider outage must surface as an error frame, not close the socket.
    provider = FailingProvider(ProviderSettings(base_url="http://x"))
    with (
        _client(provider, tmp_path, openai="sk-x") as client,
        client.websocket_connect("/ws/chat") as ws,
    ):
        ws.send_json({"session_id": "s", "message": "hi", "prefer_provider": "openai"})
        msg = ws.receive_json()
    assert msg["type"] == "error"
    assert msg["code"] == "provider_request_error"


# --- engineering endpoints ------------------------------------------------


def test_plan_endpoint(tmp_path: Path) -> None:
    (tmp_path / "svc.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    provider = ScriptedProvider("1. Inspect handler\n2. Add logging")
    with _client(provider, tmp_path, openai="sk-x") as client:
        res = client.post("/plan", json={"task": "improve handler"})
    assert res.status_code == 200
    steps = [s["description"] for s in res.json()["plan"]["steps"]]
    assert steps == ["Inspect handler", "Add logging"]


def test_review_endpoint(tmp_path: Path) -> None:
    provider = ScriptedProvider("- missing tests\nSummary: ok")
    with _client(provider, tmp_path) as client:
        res = client.post("/review", json={"code": "def f(): pass"})
    assert res.json()["result"]["findings"] == ["missing tests"]


def test_review_honors_provider_preference(tmp_path: Path) -> None:
    # With a key set, preferring gemini routes there (not local ollama).
    provider = ScriptedProvider("- x\nSummary: fine")
    with _client(provider, tmp_path, gemini="g") as client:
        res = client.post(
            "/review", json={"code": "def f(): pass", "prefer_provider": "gemini"}
        )
    assert res.status_code == 200
    assert res.json()["provider"] == "gemini"


def test_implement_dry_run_then_approve(tmp_path: Path) -> None:
    provider = ScriptedProvider("print('hi')")
    with _client(provider, tmp_path, openai="sk-x") as client:
        dry = client.post(
            "/implement", json={"instruction": "make it", "target_path": "a.py"}
        ).json()
        assert dry["executed"] is False
        assert not (tmp_path / "a.py").exists()

        done = client.post(
            "/implement",
            json={"instruction": "make it", "target_path": "a.py", "approve": True},
        ).json()
        assert done["executed"] is True
    assert (tmp_path / "a.py").read_text() == "print('hi')"


def _agent_client(provider: BaseProvider, workspace: Path, **keys: str) -> TestClient:
    settings = _settings(**keys)
    app = create_app(
        settings=settings,
        memory=MemoryStore(Database()),
        router=Router(build_catalog(settings)),
        factory=FakeFactory(provider),
        workspace_root=str(workspace),
        enable_agent=True,  # trusted local backend
    )
    return TestClient(app)


def test_implement_targets_requested_workspace_when_trusted(tmp_path: Path) -> None:
    server, open_dir = tmp_path / "server", tmp_path / "open"
    server.mkdir()
    open_dir.mkdir()
    provider = ScriptedProvider("print('hi')")
    with _agent_client(provider, server, openai="sk-x") as client:
        done = client.post(
            "/implement",
            json={
                "instruction": "make it",
                "target_path": "a.py",
                "approve": True,
                "workspace": str(open_dir),
            },
        ).json()
    assert done["executed"] is True
    assert (open_dir / "a.py").read_text() == "print('hi')"
    assert not (server / "a.py").exists()


def test_implement_ignores_requested_workspace_when_untrusted(tmp_path: Path) -> None:
    # With the agent disabled (e.g. hosted), a client path must be ignored.
    server, open_dir = tmp_path / "server", tmp_path / "open"
    server.mkdir()
    open_dir.mkdir()
    provider = ScriptedProvider("print('hi')")
    with _client(provider, server, openai="sk-x") as client:  # enable_agent=False
        done = client.post(
            "/implement",
            json={
                "instruction": "make it",
                "target_path": "a.py",
                "approve": True,
                "workspace": str(open_dir),
            },
        ).json()
    assert done["executed"] is True
    assert (server / "a.py").read_text() == "print('hi')"
    assert not (open_dir / "a.py").exists()


# --- error handling -------------------------------------------------------


def test_router_error_is_structured_409(tmp_path: Path) -> None:
    # An empty catalog means the router can satisfy nothing -> structured 409.
    from aurora.app.router import ModelCatalog

    settings = _settings()
    app = create_app(
        settings=settings,
        memory=MemoryStore(Database()),
        router=Router(ModelCatalog(())),
        factory=FakeFactory(_echo()),
        workspace_root=str(tmp_path),
        transcription=TranscriptionService(transcriber=lambda a, s: ""),
    )
    with TestClient(app) as client:
        res = client.post("/chat", json={"session_id": "s", "message": "hi"})
    assert res.status_code == 409
    assert res.json()["code"] == "router_error"


# --- frontend -------------------------------------------------------------


def test_frontend_served_when_configured(tmp_path: Path) -> None:
    frontend = tmp_path / "ui"
    frontend.mkdir()
    (frontend / "index.html").write_text("<h1>AURORA UI</h1>", encoding="utf-8")
    settings = _settings()
    app = create_app(
        settings=settings,
        memory=MemoryStore(Database()),
        router=Router(build_catalog(settings)),
        factory=FakeFactory(_echo()),
        workspace_root=str(tmp_path),
        frontend_dir=str(frontend),
    )
    with TestClient(app) as client:
        res = client.get("/")
    assert res.status_code == 200
    assert "AURORA UI" in res.text
    assert "text/html" in res.headers["content-type"]


def test_no_frontend_route_when_not_configured(tmp_path: Path) -> None:
    with _client(_echo(), tmp_path) as client:
        assert client.get("/").status_code == 404


# --- voice / transcription ------------------------------------------------


def test_transcribe_returns_text(tmp_path: Path) -> None:
    with _client(_echo(), tmp_path) as client:
        res = client.post(
            "/transcribe",
            files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert res.status_code == 200
    assert res.json() == {"text": "hello from voice"}


def test_transcribe_requires_audio(tmp_path: Path) -> None:
    with _client(_echo(), tmp_path) as client:
        assert client.post("/transcribe").status_code == 422


# --- capabilities (gates the attach / mic buttons) ------------------------


def test_capabilities_all_off_without_keys(tmp_path: Path) -> None:
    # Only local Ollama is available -> no vision, no audio provider.
    with _client(_echo(), tmp_path) as client:
        caps = client.get("/capabilities").json()
    assert caps == {"vision": False, "audio": False, "agent": False}


def test_capabilities_unlock_with_multimodal_key(tmp_path: Path) -> None:
    # A Gemini key brings a vision-capable model and an audio-capable provider.
    with _client(_echo(), tmp_path, gemini="g") as client:
        caps = client.get("/capabilities").json()
    assert caps == {"vision": True, "audio": True, "agent": False}


def test_capabilities_audio_requires_transcription_backend(tmp_path: Path) -> None:
    # A vision key alone still can't enable audio if transcription is unavailable.
    settings = _settings(gemini="g")
    app = create_app(
        settings=settings,
        memory=MemoryStore(Database()),
        router=Router(build_catalog(settings)),
        factory=FakeFactory(_echo()),
        workspace_root=str(tmp_path),
        transcription=TranscriptionService(),  # no faster-whisper in CI
    )
    with TestClient(app) as client:
        caps = client.get("/capabilities").json()
    assert caps["vision"] is True
    # audio hinges on the whisper backend being installed in this environment.
    assert caps["audio"] == TranscriptionService().available()


# --- runtime key connection -----------------------------------------------


def test_keys_endpoint_activates_provider(tmp_path: Path) -> None:
    with _client(_echo(), tmp_path) as client:
        res = client.post("/keys", json={"keys": {"groq": "gk-live"}})
    assert res.status_code == 200
    body = res.json()
    assert body["updated"] == ["groq"]
    assert "groq" in body["available"]

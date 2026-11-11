from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from aurora.app.api import create_app
from aurora.app.auth import SessionSigner
from aurora.app.config.models import AppSettings, ProviderSettings
from aurora.app.database import Database
from aurora.app.memory import MemoryStore
from aurora.app.router import Router, build_catalog
from tests.app.test_api import FakeFactory, _echo

PUBLIC_URL = "https://aurora.test"
GOOGLE_PROFILE = {
    "sub": "1001",
    "email": "ada@example.com",
    "email_verified": True,
    "name": "Ada",
    "picture": "https://img.test/ada.png",
}


def _google_transport(profile: dict | None = None, token_ok: bool = True):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            if not token_ok:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "token-1"})
        return httpx.Response(200, json=profile or GOOGLE_PROFILE)

    return httpx.MockTransport(handler)


def _settings(configured: bool = True) -> AppSettings:
    providers = {"ollama": ProviderSettings(base_url="http://localhost:11434")}
    if not configured:
        return AppSettings(providers=providers)
    return AppSettings(
        providers=providers,
        google_client_id="client-id",
        google_client_secret="client-secret",
        auth_secret="s" * 32,
        public_url=PUBLIC_URL,
    )


def _client(
    tmp_path: Path,
    configured: bool = True,
    profile: dict | None = None,
    token_ok: bool = True,
) -> TestClient:
    settings = _settings(configured)
    http = httpx.AsyncClient(transport=_google_transport(profile, token_ok))
    app = create_app(
        settings=settings,
        memory=MemoryStore(Database()),
        router=Router(build_catalog(settings)),
        factory=FakeFactory(_echo()),
        workspace_root=str(tmp_path),
        google_http=http,
    )
    return TestClient(app, base_url=PUBLIC_URL, follow_redirects=False)


def _sign_in(client: TestClient) -> None:
    login = client.get("/auth/google/login")
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    client.get("/auth/google/callback", params={"code": "abc", "state": state})


def test_config_reports_whether_google_is_set_up(tmp_path: Path) -> None:
    with _client(tmp_path) as on, _client(tmp_path, configured=False) as off:
        assert on.get("/auth/config").json() == {"google": True}
        assert off.get("/auth/config").json() == {"google": False}
        assert off.get("/auth/google/login").status_code == 400


def test_login_redirects_to_google_with_state(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        res = client.get("/auth/google/login")
    target = urlparse(res.headers["location"])
    query = parse_qs(target.query)
    assert res.status_code == 307
    assert target.netloc == "accounts.google.com"
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == [f"{PUBLIC_URL}/auth/google/callback"]
    assert query["state"][0] in res.headers["set-cookie"]


def test_callback_signs_the_user_in(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/auth/me").json() == {"user": None}
        _sign_in(client)
        me = client.get("/auth/me").json()["user"]
    assert me["email"] == "ada@example.com"
    assert me["name"] == "Ada"


def test_callback_rejects_a_wrong_state(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        client.get("/auth/google/login")
        res = client.get(
            "/auth/google/callback", params={"code": "abc", "state": "forged"}
        )
        assert res.headers["location"] == "/?signin=failed"
        assert client.get("/auth/me").json() == {"user": None}


def test_callback_rejects_a_google_failure(tmp_path: Path) -> None:
    with _client(tmp_path, token_ok=False) as client:
        _sign_in(client)
        assert client.get("/auth/me").json() == {"user": None}


def test_callback_rejects_an_unverified_email(tmp_path: Path) -> None:
    profile = {**GOOGLE_PROFILE, "email_verified": False}
    with _client(tmp_path, profile=profile) as client:
        _sign_in(client)
        assert client.get("/auth/me").json() == {"user": None}


def test_logout_clears_the_session(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        client.post("/auth/logout")
        assert client.get("/auth/me").json() == {"user": None}


def test_forged_session_cookie_is_ignored(tmp_path: Path) -> None:
    forged = SessionSigner("another-secret-another-secret-12").issue(
        {"id": "9", "email": "x@y.z", "name": "X"}
    )
    with _client(tmp_path) as client:
        client.cookies.set("aurora_session", forged)
        assert client.get("/auth/me").json() == {"user": None}
        assert client.get("/chats").status_code == 401


def test_chats_require_sign_in(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/chats").status_code == 401
        assert client.get("/chats/abcdef123").status_code == 401
        assert client.delete("/chats/abcdef123").status_code == 401


def _cookie_header(client: TestClient) -> dict[str, str]:
    jar = "; ".join(f"{name}={value}" for name, value in client.cookies.items())
    return {"cookie": jar} if jar else {}


def _say(client: TestClient, chat_id: str, text: str) -> None:
    with client.websocket_connect("/ws/chat", headers=_cookie_header(client)) as ws:
        ws.send_json({"session_id": chat_id, "message": text})
        while ws.receive_json()["type"] not in {"done", "error"}:
            pass


def test_signed_in_chats_are_saved_and_listed(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        _say(client, "chat-aaaa1", "first question")
        _say(client, "chat-aaaa1", "second question")
        _say(client, "chat-bbbb2", "another topic")
        chats = client.get("/chats").json()["chats"]
        saved = client.get("/chats/chat-aaaa1").json()["messages"]
    assert {c["id"] for c in chats} == {"chat-aaaa1", "chat-bbbb2"}
    assert all(c["title"] for c in chats)
    assert [m["role"] for m in saved] == ["user", "assistant", "user", "assistant"]
    assert saved[0]["content"] == "first question"


def test_chats_belong_to_their_own_account(tmp_path: Path) -> None:
    with _client(tmp_path) as ada:
        _sign_in(ada)
        _say(ada, "chat-aaaa1", "ada secret")
        memory_chats = ada.get("/chats").json()["chats"]
    other = {**GOOGLE_PROFILE, "sub": "2002", "email": "bob@example.com", "name": "Bob"}
    with _client(tmp_path, profile=other) as bob:
        _sign_in(bob)
        assert bob.get("/chats").json()["chats"] == []
        assert bob.get("/chats/chat-aaaa1").json()["messages"] == []
    assert len(memory_chats) == 1


def test_delete_removes_a_saved_chat(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        _say(client, "chat-aaaa1", "to delete")
        assert client.delete("/chats/chat-aaaa1").json() == {"ok": True}
        assert client.get("/chats").json()["chats"] == []


def test_guests_cannot_reach_account_sessions(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        res = client.post(
            "/chat", json={"session_id": "u:1001:chat-aaaa1", "message": "hi"}
        )
        assert res.status_code == 400
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"session_id": "u:1001:chat-aaaa1", "message": "hi"})
            assert ws.receive_json()["type"] == "error"


def test_signed_in_user_cannot_use_an_invalid_chat_id(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        with client.websocket_connect("/ws/chat", headers=_cookie_header(client)) as ws:
            ws.send_json({"session_id": "../x", "message": "hi"})
            assert ws.receive_json()["type"] == "error"


def test_session_signer_rejects_tampering_and_expiry() -> None:
    now = [1000.0]
    signer = SessionSigner("k" * 32, ttl_seconds=60, clock=lambda: now[0])
    token = signer.issue({"id": "1"})
    assert signer.read(token)["id"] == "1"
    assert signer.read(token + "x") is None
    assert signer.read("not-a-token") is None
    now[0] = 2000.0
    assert signer.read(token) is None


def test_websocket_rejects_other_sites(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        with client.websocket_connect("/ws/chat", headers={"origin": PUBLIC_URL}) as ws:
            ws.send_json({"session_id": "s", "message": "hi"})
            assert ws.receive_json()["type"] in {"token", "done"}
        try:
            with client.websocket_connect(
                "/ws/chat", headers={"origin": "https://evil.example"}
            ):
                rejected = False
        except WebSocketDisconnect:
            rejected = True
    assert rejected


def test_rename_changes_the_listed_title(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        _say(client, "chat-aaaa1", "first question")
        assert client.patch(
            "/chats/chat-aaaa1", json={"title": "  Trip   plans "}
        ).json() == {"title": "Trip plans"}
        chats = client.get("/chats").json()["chats"]
    assert chats[0]["title"] == "Trip plans"


def test_rename_rejects_blank_or_unknown_chats(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        _say(client, "chat-aaaa1", "question")
        assert client.patch("/chats/chat-aaaa1", json={"title": "   "}).status_code == 400
        assert (
            client.patch("/chats/chat-aaaa1", json={"title": "x" * 61}).status_code == 400
        )
        assert (
            client.patch("/chats/chat-zzzz9", json={"title": "Nope"}).status_code == 400
        )


def test_search_matches_titles_and_message_text(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        _say(client, "chat-aaaa1", "plan my Dubai trip")
        _say(client, "chat-bbbb2", "fix the 100% broken build_step")
        by_title = [
            c["id"] for c in client.get("/chats", params={"q": "dubai"}).json()["chats"]
        ]
        by_text = [
            c["id"]
            for c in client.get("/chats", params={"q": "build_step"}).json()["chats"]
        ]
        literal_percent = [
            c["id"] for c in client.get("/chats", params={"q": "100%"}).json()["chats"]
        ]
        none = client.get("/chats", params={"q": "nothing-like-this"}).json()["chats"]
    assert by_title == ["chat-aaaa1"]
    assert by_text == ["chat-bbbb2"]
    assert literal_percent == ["chat-bbbb2"]
    assert none == []


def test_share_link_is_read_only_and_can_be_revoked(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        _say(client, "chat-aaaa1", "shared question")
        token = client.post("/chats/chat-aaaa1/share").json()["token"]
        assert client.post("/chats/chat-aaaa1/share").json()["token"] == token
        client.cookies.clear()
        shared = client.get(f"/shared/{token}").json()["messages"]
        assert shared[0] == {"role": "user", "content": "shared question"}
        assert client.get("/shared/not-a-real-token-123456").status_code == 400
        _sign_in(client)
        assert client.delete("/chats/chat-aaaa1/share").json() == {"ok": True}
        client.cookies.clear()
        assert client.get(f"/shared/{token}").status_code == 400


def test_delete_also_removes_the_title_and_share_link(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        _say(client, "chat-aaaa1", "to delete")
        client.patch("/chats/chat-aaaa1", json={"title": "Old name"})
        token = client.post("/chats/chat-aaaa1/share").json()["token"]
        client.delete("/chats/chat-aaaa1")
        assert client.get("/chats").json()["chats"] == []
        client.cookies.clear()
        assert client.get(f"/shared/{token}").status_code == 400


def test_share_and_rename_require_sign_in(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.patch("/chats/chat-aaaa1", json={"title": "x"}).status_code == 401
        assert client.post("/chats/chat-aaaa1/share").status_code == 401


async def test_revoking_removes_orphaned_share_tokens_too() -> None:
    memory = MemoryStore(Database())
    await memory.open()
    await memory.kv.set("shared_tokens", "token-from-a-race-1234", "u:1:chat-aaaa1")
    await memory.kv.set("shared_tokens", "token-that-won-5678", "u:1:chat-aaaa1")
    await memory.kv.set("shared_tokens", "other-chat-token-9999", "u:1:chat-bbbb2")
    await memory.kv.delete_by_value("shared_tokens", "u:1:chat-aaaa1")
    remaining = await memory.kv.items("shared_tokens")
    await memory.close()
    assert remaining == {"other-chat-token-9999": "u:1:chat-bbbb2"}


def test_guest_chat_snapshot_is_shareable_without_an_account(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        created = client.post(
            "/shares",
            json={
                "title": "Dubai trip",
                "messages": [
                    {"role": "user", "content": "plan it"},
                    {"role": "assistant", "content": "Book early."},
                ],
            },
        ).json()
        client.cookies.clear()
        shared = client.get(f"/shared/{created['token']}").json()
        assert shared["title"] == "Dubai trip"
        assert shared["messages"][1] == {"role": "assistant", "content": "Book early."}
        assert client.delete(f"/shares/{created['manage']}").json() == {"ok": True}
        assert client.get(f"/shared/{created['token']}").status_code == 400


def test_snapshot_rejects_empty_or_oversized_chats(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.post("/shares", json={"messages": []}).status_code == 400
        assert (
            client.post(
                "/shares", json={"messages": [{"role": "system", "content": "x"}]}
            ).status_code
            == 422
        )
        long_text = "x" * 20001
        assert (
            client.post(
                "/shares", json={"messages": [{"role": "user", "content": long_text}]}
            ).status_code
            == 400
        )
        assert client.delete("/shares/not-valid").status_code == 400


def _say_until_title(client: TestClient, chat_id: str, text: str) -> str:
    with client.websocket_connect("/ws/chat", headers=_cookie_header(client)) as ws:
        ws.send_json({"session_id": chat_id, "message": text})
        while True:
            event = ws.receive_json()
            if event["type"] == "title":
                return event["title"]


def test_first_reply_names_the_chat_until_renamed_by_hand(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _sign_in(client)
        title = _say_until_title(client, "chat-aaaa1", "plan my trip")
        assert client.get("/chats").json()["chats"][0]["title"] == title
        client.patch("/chats/chat-aaaa1", json={"title": "My holiday"})
        _say(client, "chat-aaaa1", "second")
        _say_until_title(client, "chat-aaaa1", "third")
        assert client.get("/chats").json()["chats"][0]["title"] == "My holiday"


def test_snapshot_shares_are_rate_limited_per_address(tmp_path: Path) -> None:
    body = {"messages": [{"role": "user", "content": "hi"}]}
    with _client(tmp_path) as client:
        statuses = [client.post("/shares", json=body).status_code for _ in range(11)]
    assert statuses[:10] == [200] * 10
    assert statuses[10] == 400


def test_snapshot_is_marked_unverified_and_server_share_verified(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        token = client.post(
            "/shares", json={"messages": [{"role": "user", "content": "hi"}]}
        ).json()["token"]
        assert client.get(f"/shared/{token}").json()["verified"] is False
        _sign_in(client)
        _say(client, "chat-aaaa1", "hello")
        live = client.post("/chats/chat-aaaa1/share").json()["token"]
        assert client.get(f"/shared/{live}").json()["verified"] is True

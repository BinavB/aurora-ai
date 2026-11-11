from __future__ import annotations

import re
import secrets
from collections.abc import Mapping
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from aurora.app.auth import (
    AccountUser,
    AuthRequiredError,
    GoogleOAuth,
    SessionSigner,
    SignInError,
)
from aurora.app.core.exceptions import ConfigurationError, ValidationError
from aurora.app.memory.store import MemoryStore

SESSION_COOKIE = "aurora_session"
STATE_COOKIE = "aurora_oauth_state"
STATE_TTL_SECONDS = 600
USER_SESSION_PREFIX = "u:"
CHAT_LIST_LIMIT = 50
TITLE_LIMIT = 60
_CHAT_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
SHARED_NAMESPACE = "shared_tokens"


def _titles_namespace(user: AccountUser) -> str:
    return f"chat_titles:{user.id}"


def _shares_namespace(user: AccountUser) -> str:
    return f"chat_shares:{user.id}"


class RenameBody(BaseModel):
    title: str


def user_from_cookies(
    signer: SessionSigner | None, cookies: Mapping[str, str]
) -> AccountUser | None:
    if signer is None:
        return None
    body = signer.read(cookies.get(SESSION_COOKIE))
    if body is None:
        return None
    try:
        return AccountUser(
            id=body["id"],
            email=body["email"],
            name=body["name"],
            picture=body.get("picture", ""),
        )
    except (KeyError, ValueError):
        return None


def resolve_session_id(user: AccountUser | None, requested: str) -> str:
    if user is None:
        if requested.startswith(USER_SESSION_PREFIX):
            raise ValidationError("Sign in to open saved chats")
        return requested
    if not _CHAT_ID.match(requested):
        raise ValidationError("Invalid chat id")
    return f"{_user_prefix(user)}{requested}"


def same_origin(headers: Mapping[str, str], public_url: str | None) -> bool:
    origin = headers.get("origin")
    if not origin:
        return True
    host = urlparse(origin).netloc
    allowed = {headers.get("host", ""), headers.get("x-forwarded-host", "")}
    if public_url:
        allowed.add(urlparse(public_url).netloc)
    return host in allowed - {""}


def _user_prefix(user: AccountUser) -> str:
    return f"{USER_SESSION_PREFIX}{user.id}:"


def _title(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= TITLE_LIMIT else flat[: TITLE_LIMIT - 1] + "…"


def _base_url(request: Request, public_url: str | None) -> str:
    if public_url:
        return public_url
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    return f"{scheme}://{host}"


def install_account_routes(
    app: FastAPI,
    *,
    memory: MemoryStore,
    google: GoogleOAuth | None,
    signer: SessionSigner | None,
    public_url: str | None,
) -> None:
    def require_user(request: Request) -> AccountUser:
        user = user_from_cookies(signer, request.cookies)
        if user is None:
            raise AuthRequiredError("Sign in to see your saved chats")
        return user

    @app.get("/auth/config")
    async def auth_config() -> dict[str, bool]:
        return {"google": google is not None}

    @app.get("/auth/me")
    async def auth_me(request: Request) -> dict[str, dict | None]:
        user = user_from_cookies(signer, request.cookies)
        return {"user": user.model_dump() if user else None}

    @app.get("/auth/google/login")
    async def google_login(request: Request) -> Response:
        if google is None:
            raise ConfigurationError("Google sign-in is not set up")
        state = secrets.token_urlsafe(24)
        redirect_uri = _base_url(request, public_url) + "/auth/google/callback"
        response = RedirectResponse(google.authorization_url(redirect_uri, state))
        response.set_cookie(
            STATE_COOKIE,
            state,
            max_age=STATE_TTL_SECONDS,
            httponly=True,
            secure=redirect_uri.startswith("https://"),
            samesite="lax",
        )
        return response

    @app.get("/auth/google/callback")
    async def google_callback(
        request: Request, code: str = "", state: str = ""
    ) -> Response:
        expected = request.cookies.get(STATE_COOKIE, "")
        valid = bool(code) and bool(state) and secrets.compare_digest(state, expected)
        if google is None or signer is None or not valid:
            return _failed()
        redirect_uri = _base_url(request, public_url) + "/auth/google/callback"
        try:
            user = await google.user_from_code(code, redirect_uri)
        except SignInError:
            return _failed()
        response = RedirectResponse("/")
        response.set_cookie(
            SESSION_COOKIE,
            signer.issue(user.model_dump()),
            max_age=signer.ttl_seconds,
            httponly=True,
            secure=redirect_uri.startswith("https://"),
            samesite="lax",
        )
        response.delete_cookie(STATE_COOKIE)
        return response

    @app.post("/auth/logout")
    async def logout() -> Response:
        response = JSONResponse({"ok": True})
        response.delete_cookie(SESSION_COOKIE)
        return response

    @app.get("/chats")
    async def list_chats(
        request: Request, q: str = ""
    ) -> dict[str, list[dict[str, str]]]:
        user = require_user(request)
        prefix = _user_prefix(user)
        titles = await memory.kv.items(_titles_namespace(user))
        summaries = await memory.chat_summaries(prefix, CHAT_LIST_LIMIT)
        needle = " ".join(q.split()).lower()
        matched = set(await memory.chats_containing(prefix, needle)) if needle else set()
        chats = []
        for item in summaries:
            title = (
                _title(titles.get(item.session_id[len(prefix) :]) or item.title)
                or "New chat"
            )
            if needle and needle not in title.lower() and item.session_id not in matched:
                continue
            chats.append(
                {
                    "id": item.session_id[len(prefix) :],
                    "title": title,
                    "updated_at": item.updated_at,
                }
            )
        return {"chats": chats}

    @app.get("/chats/{chat_id}")
    async def read_chat(
        chat_id: str, request: Request
    ) -> dict[str, list[dict[str, str]]]:
        user = require_user(request)
        history = await memory.conversation(resolve_session_id(user, chat_id))
        return {
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in history
            ]
        }

    @app.patch("/chats/{chat_id}")
    async def rename_chat(
        chat_id: str, body: RenameBody, request: Request
    ) -> dict[str, str]:
        user = require_user(request)
        session_id = resolve_session_id(user, chat_id)
        title = " ".join(body.title.split())
        if not title or len(title) > TITLE_LIMIT:
            raise ValidationError(f"Name must be 1 to {TITLE_LIMIT} characters")
        if not await memory.conversation(session_id):
            raise ValidationError("Chat not found")
        await memory.kv.set(_titles_namespace(user), chat_id, title)
        return {"title": title}

    @app.delete("/chats/{chat_id}")
    async def delete_chat(chat_id: str, request: Request) -> dict[str, bool]:
        user = require_user(request)
        session_id = resolve_session_id(user, chat_id)
        await _revoke_share(memory, user, chat_id, session_id)
        await memory.kv.delete(_titles_namespace(user), chat_id)
        await memory.clear_conversation(session_id)
        return {"ok": True}

    @app.post("/chats/{chat_id}/share")
    async def share_chat(chat_id: str, request: Request) -> dict[str, str]:
        user = require_user(request)
        session_id = resolve_session_id(user, chat_id)
        if not await memory.conversation(session_id):
            raise ValidationError("Chat not found")
        token = await memory.kv.get(_shares_namespace(user), chat_id)
        if not token:
            token = secrets.token_urlsafe(18)
            await memory.kv.set(SHARED_NAMESPACE, token, session_id)
            await memory.kv.set(_shares_namespace(user), chat_id, token)
        return {"token": token}

    @app.delete("/chats/{chat_id}/share")
    async def unshare_chat(chat_id: str, request: Request) -> dict[str, bool]:
        user = require_user(request)
        await _revoke_share(memory, user, chat_id, resolve_session_id(user, chat_id))
        return {"ok": True}

    @app.get("/shared/{token}")
    async def read_shared_chat(token: str) -> dict[str, list[dict[str, str]]]:
        session_id = (
            await memory.kv.get(SHARED_NAMESPACE, token) if _TOKEN.match(token) else None
        )
        if session_id is None:
            raise ValidationError("This shared chat is no longer available")
        history = await memory.conversation(session_id)
        return {
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in history
                if message.role.value in {"user", "assistant"}
            ]
        }


async def _revoke_share(
    memory: MemoryStore, user: AccountUser, chat_id: str, session_id: str
) -> None:
    await memory.kv.delete_by_value(SHARED_NAMESPACE, session_id)
    await memory.kv.delete(_shares_namespace(user), chat_id)


def _failed() -> Response:
    response = RedirectResponse("/?signin=failed")
    response.delete_cookie(STATE_COOKIE)
    return response

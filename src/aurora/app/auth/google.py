from __future__ import annotations

from urllib.parse import urlencode

import httpx

from aurora.app.auth.errors import SignInError
from aurora.app.auth.models import AccountUser

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = "openid email profile"
REQUEST_TIMEOUT_SECONDS = 15.0


class GoogleOAuth:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = client

    def authorization_url(self, redirect_uri: str, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": SCOPES,
                "state": state,
                "prompt": "select_account",
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def user_from_code(self, code: str, redirect_uri: str) -> AccountUser:
        client = self._client or httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            access_token = await self._exchange(client, code, redirect_uri)
            return await self._profile(client, access_token)
        except httpx.HTTPError as exc:
            raise SignInError("Could not reach Google to finish signing in") from exc
        finally:
            if self._client is None:
                await client.aclose()

    async def _exchange(
        self, client: httpx.AsyncClient, code: str, redirect_uri: str
    ) -> str:
        response = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token = response.json().get("access_token") if response.is_success else None
        if not token:
            raise SignInError("Google did not accept the sign-in")
        return token

    async def _profile(self, client: httpx.AsyncClient, access_token: str) -> AccountUser:
        response = await client.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        data = response.json() if response.is_success else {}
        if not data.get("sub") or not data.get("email"):
            raise SignInError("Google did not return an account")
        if data.get("email_verified") is False:
            raise SignInError("This Google email is not verified")
        return AccountUser(
            id=str(data["sub"]),
            email=data["email"],
            name=data.get("name") or data["email"],
            picture=data.get("picture") or "",
        )

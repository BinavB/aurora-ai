from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from typing import Any

SESSION_TTL_SECONDS = 30 * 24 * 60 * 60


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class SessionSigner:
    def __init__(
        self,
        secret: str,
        ttl_seconds: int = SESSION_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._key = secret.encode("utf-8")
        self._ttl = ttl_seconds
        self._clock = clock

    @property
    def ttl_seconds(self) -> int:
        return self._ttl

    def issue(self, payload: dict[str, Any]) -> str:
        body = {**payload, "exp": int(self._clock()) + self._ttl}
        encoded = _encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
        return f"{encoded}.{self._signature(encoded)}"

    def read(self, token: str | None) -> dict[str, Any] | None:
        if not token or token.count(".") != 1:
            return None
        encoded, signature = token.split(".")
        if not hmac.compare_digest(signature, self._signature(encoded)):
            return None
        try:
            body = json.loads(_decode(encoded))
        except ValueError:
            return None
        if not isinstance(body, dict) or body.get("exp", 0) < self._clock():
            return None
        return body

    def _signature(self, encoded: str) -> str:
        digest = hmac.new(self._key, encoded.encode("ascii"), hashlib.sha256).digest()
        return _encode(digest)

from __future__ import annotations

from pydantic import BaseModel


class AccountUser(BaseModel):
    id: str
    email: str
    name: str
    picture: str = ""

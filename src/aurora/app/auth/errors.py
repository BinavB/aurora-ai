from __future__ import annotations

from aurora.app.core.exceptions import AuroraError


class SignInError(AuroraError):
    code = "sign_in_error"


class AuthRequiredError(AuroraError):
    code = "unauthorized"

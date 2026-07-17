from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.models.user import User


AuthReason = Literal[
    'success',
    'invalid_credentials',
    'database_unavailable',
    'user_inactive',
    'provider_unavailable',
]


@dataclass(frozen=True)
class AuthResult:
    success: bool
    reason: AuthReason
    source: str = 'database'
    user: User | None = None
    message: str | None = None


INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
DATABASE_UNAVAILABLE_MESSAGE = 'Login service is temporarily unavailable. Please check the database connection.'
PROVIDER_UNAVAILABLE_MESSAGE = 'External authentication provider is temporarily unavailable. Contact an administrator.'
USER_INACTIVE_MESSAGE = 'This account is currently inactive. Contact an administrator to restore access.'

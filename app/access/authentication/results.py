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
    'identity_not_provisioned',
    'access_not_permitted',
    'state_mismatch',
    'authorization_denied',
    'authorization_code_missing',
    'rate_limited',
]


@dataclass(frozen=True)
class AuthResult:
    success: bool
    reason: AuthReason
    source: str = 'database'
    user: User | None = None
    message: str | None = None


INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
DATABASE_UNAVAILABLE_MESSAGE = (
    'Sign-in service is temporarily unavailable. Try again later or contact an administrator.'
)
PROVIDER_UNAVAILABLE_MESSAGE = 'External authentication provider is temporarily unavailable. Contact an administrator.'
USER_INACTIVE_MESSAGE = 'This account is currently inactive. Contact an administrator to restore access.'
ACCESS_NOT_PERMITTED_MESSAGE = 'This account does not currently have an active KAORI access assignment.'

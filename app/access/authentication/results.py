from __future__ import annotations

from dataclasses import dataclass, field
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
    'account_gate_rejected',
    'bot_challenge_failed',
]


@dataclass(frozen=True)
class LocalCredentialProof:
    """Request-local snapshot of the exact verified Local Database credential."""

    password_hash: str = field(repr=False)
    generation: int


@dataclass(frozen=True)
class ExternalCredentialProof:
    """Non-secret exact provider instance, revision and provisioned identity binding."""

    provider_id: int
    revision: int
    link_id: int


@dataclass(frozen=True)
class AuthResult:
    success: bool
    reason: AuthReason
    source: str = 'database'
    user: User | None = None
    message: str | None = None
    local_credential_proof: LocalCredentialProof | None = field(default=None, repr=False, compare=False)
    external_credential_proof: ExternalCredentialProof | None = field(default=None, repr=False, compare=False)


INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
DATABASE_UNAVAILABLE_MESSAGE = (
    'Sign-in service is temporarily unavailable. Try again later or contact an administrator.'
)
PROVIDER_UNAVAILABLE_MESSAGE = 'External authentication provider is temporarily unavailable. Contact an administrator.'
USER_INACTIVE_MESSAGE = 'This account is currently inactive. Contact an administrator to restore access.'
ACCESS_NOT_PERMITTED_MESSAGE = 'This account does not currently have an active KAORI access assignment.'

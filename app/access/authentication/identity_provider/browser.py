from __future__ import annotations

import hashlib
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from hmac import compare_digest
from math import isfinite
from typing import Protocol, runtime_checkable

from app.models import IdentityProvider


class SsoProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SsoIdentity:
    subject: str
    username: str
    email: str | None
    display_name: str | None
    avatar_url: str | None = None
    email_verified: bool = False


@runtime_checkable
class BrowserSsoAdapter(Protocol):
    adapter_key: str
    requires_nonce: bool

    def build_authorization_url(
        self,
        provider: IdentityProvider,
        *,
        redirect_uri: str,
        state: str,
        nonce: str | None,
    ) -> str: ...

    def exchange_code(
        self,
        provider: IdentityProvider,
        *,
        code: str,
        redirect_uri: str,
        expected_nonce: str | None,
    ) -> SsoIdentity: ...

    def validate_configuration(self, provider: IdentityProvider) -> str: ...


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def generate_nonce() -> str:
    return secrets.token_urlsafe(32)


def state_fingerprint(state: str) -> str:
    return hashlib.sha256(state.encode('utf-8')).hexdigest()


def _parse_session_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _parse_session_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    parsed: float
    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
    else:
        return None
    return parsed if isfinite(parsed) else None


def sso_flow_is_valid(
    flow: Mapping[str, object],
    *,
    provider_id: int,
    supplied_state: str,
    now_timestamp: float,
    ttl_seconds: int,
) -> bool:
    expected_provider_id = _parse_session_int(flow.get('provider_id'))
    started_at = _parse_session_float(flow.get('started_at'))
    if expected_provider_id is None or started_at is None:
        return False

    expected_hash = str(flow.get('state_hash') or '')
    if not supplied_state or not expected_hash:
        return False
    if expected_provider_id != provider_id:
        return False
    if not compare_digest(state_fingerprint(supplied_state), expected_hash):
        return False

    bounded_ttl = max(1, int(ttl_seconds))
    age_seconds = now_timestamp - started_at
    return started_at > 0 and 0 <= age_seconds <= bounded_ttl


def load_client_secret(provider: IdentityProvider) -> str:
    env_name = str((provider.configuration_json or {}).get('client_secret_env') or '').strip()
    if not env_name:
        raise SsoProviderError('Client secret environment-variable name is not configured.')
    value = os.getenv(env_name)
    if not value:
        raise SsoProviderError(f'The environment variable {env_name} is not available to KAORI.')
    return value


def request_timeout_seconds(provider: IdentityProvider) -> int:
    try:
        value = int((provider.configuration_json or {}).get('connect_timeout_seconds') or 5)
    except (TypeError, ValueError):
        value = 5
    return max(2, min(value, 30))

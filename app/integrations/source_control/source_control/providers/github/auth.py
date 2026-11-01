"""GitHub App RS256 JWT construction (SC-02, #2741).

Uses the already-installed cryptography package. Private PEM never enters
committed Source Control identity, logs, JobExecution or OAuth SSO.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class GitHubAppAuthError(ValueError):
    """Public, sanitized GitHub App auth failure."""


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _positive_provider_id(value: str | int) -> int:
    if isinstance(value, bool):
        raise GitHubAppAuthError('GitHub App identity must be a positive numeric ID.')
    text = str(value).strip()
    if not text.isascii() or not text.isdecimal() or int(text) <= 0:
        raise GitHubAppAuthError('GitHub App identity must be a positive numeric ID.')
    return int(text)


def build_app_jwt(app_id: str | int, private_key_pem: str, *, now: datetime | None = None) -> str:
    """Sign a short-lived GitHub App JWT. No external request or token cache.

    GitHub permits up to ten minutes. Backdate iat for clock skew and keep exp
    below that limit. Supply now explicitly only for deterministic tests.
    """
    identifier = _positive_provider_id(app_id)
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        raise GitHubAppAuthError('GitHub App signing time must be timezone-aware.')
    issued = int(current.timestamp())
    if not private_key_pem or not isinstance(private_key_pem, str):
        raise GitHubAppAuthError('GitHub App signing credential is unavailable.')
    try:
        key = serialization.load_pem_private_key(private_key_pem.encode('utf-8'), password=None)
    except (TypeError, ValueError) as exc:
        raise GitHubAppAuthError('GitHub App signing credential is invalid.') from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise GitHubAppAuthError('GitHub App signing credential must be an RSA private key.')
    header = _b64url(json.dumps({'alg': 'RS256', 'typ': 'JWT'}, separators=(',', ':')).encode('ascii'))
    claims = _b64url(
        json.dumps({'iat': issued - 60, 'exp': issued + 480, 'iss': str(identifier)}, separators=(',', ':')).encode(
            'ascii'
        )
    )
    signing_input = f'{header}.{claims}'.encode('ascii')
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f'{header}.{claims}.{_b64url(signature)}'

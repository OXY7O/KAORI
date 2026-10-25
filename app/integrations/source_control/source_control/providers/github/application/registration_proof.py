"""Short-lived GitHub App registration proof after a successful live test.

The signed token contains only the requesting user and a keyed fingerprint.
Raw credentials, webhook secrets, and installation access tokens never enter
the proof, session, logs, or asynchronous job arguments.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.integrations.source_control.source_control.providers.github.registration import (
    GitHubConnectionInput,
)

_PROOF_SALT = 'source-control-github-app-registration-proof-v1'
REGISTRATION_PROOF_MAX_AGE_SECONDS = 600


def _canonical_multiline(value: str | None) -> str | None:
    """Match browser native FormData and HTMX newline serialization.

    The original credential remains unchanged for GitHub authentication and
    encrypted persistence. Only the keyed proof fingerprint is normalized.
    """
    return value.replace('\r\n', '\n').replace('\r', '\n') if value is not None else None


def _fingerprint(values: GitHubConnectionInput) -> str:
    payload = json.dumps(
        {
            'name': values.name,
            'environment': values.environment,
            'description': _canonical_multiline(values.description),
            'app_id': str(values.app_id),
            'installation_id': str(values.installation_id),
            'account_id': str(values.account_id),
            'private_key_pem': _canonical_multiline(values.private_key_pem),
            'webhook_secret': values.webhook_secret,
            'enabled': bool(values.enabled),
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
    )
    secret = current_app.config['SECRET_KEY']
    key = secret if isinstance(secret, bytes) else str(secret).encode('utf-8')
    return hmac.new(key, payload.encode('utf-8'), hashlib.sha256).hexdigest()


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=current_app.config['SECRET_KEY'],
        salt=_PROOF_SALT,
    )


def issue_github_registration_proof(*, user_id: int, values: GitHubConnectionInput) -> str:
    """Issue only after successful provider-owned Test Connection."""
    return _serializer().dumps(
        {
            'user_id': int(user_id),
            'fingerprint': _fingerprint(values),
        }
    )


def verify_github_registration_proof(
    *, token: str | None, user_id: int, values: GitHubConnectionInput
) -> tuple[bool, str]:
    """Reject missing, expired, tampered, cross-user or changed submissions."""
    if not token:
        return False, 'Run Test Connection before registering this GitHub App.'
    try:
        payload = _serializer().loads(token, max_age=REGISTRATION_PROOF_MAX_AGE_SECONDS)
    except SignatureExpired:
        return False, 'The connection test expired. Run Test Connection again.'
    except BadSignature:
        return False, 'The connection test proof is invalid. Run Test Connection again.'
    if not isinstance(payload, dict) or payload.get('user_id') != int(user_id):
        return False, 'The connection test belongs to another user. Run Test Connection again.'
    if not hmac.compare_digest(str(payload.get('fingerprint') or ''), _fingerprint(values)):
        return False, 'Connection settings changed after testing. Run Test Connection again.'
    return True, ''

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.metrics.forms import MetricsSourceForm

_REGISTRATION_PROOF_SALT = 'metrics-source-registration-proof-v1'
REGISTRATION_PROOF_MAX_AGE_SECONDS = 600
_FINGERPRINT_FIELDS = (
    'provider_key',
    'name',
    'description',
    'endpoint',
    'auth_type',
    'username',
    'password',
    'bearer_token',
    'timeout',
    'verify_ssl',
    'enabled',
    'version_detection_mode',
    'compatibility_profile_override',
)


def issue_registration_proof(*, form: MetricsSourceForm, user_id: int) -> str:
    """Issue a short-lived proof for one successfully tested draft form.

    Only the signed fingerprint and user identity are stored in the token. Raw
    credentials and endpoint values are never embedded in the proof.
    """
    return _serializer().dumps(
        {
            'user_id': int(user_id),
            'fingerprint': _form_fingerprint(form),
        }
    )


def verify_registration_proof(
    *,
    token: str | None,
    form: MetricsSourceForm,
    user_id: int,
) -> tuple[bool, str]:
    """Verify that the same user tested the same form within the allowed age."""
    if not token:
        return False, 'Run Test Connection before registering this connection.'

    try:
        payload = _serializer().loads(
            token,
            max_age=REGISTRATION_PROOF_MAX_AGE_SECONDS,
        )
    except SignatureExpired:
        return False, 'The successful connection test expired. Run Test Connection again.'
    except BadSignature:
        return False, 'The connection test proof is invalid. Run Test Connection again.'

    if int(payload.get('user_id') or 0) != int(user_id):
        return False, 'The connection test belongs to another session. Run Test Connection again.'

    if not hmac.compare_digest(
        str(payload.get('fingerprint') or ''),
        _form_fingerprint(form),
    ):
        return False, 'Connection settings changed after testing. Run Test Connection again.'

    return True, ''


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=current_app.config['SECRET_KEY'],
        salt=_REGISTRATION_PROOF_SALT,
    )


def _form_fingerprint(form: MetricsSourceForm) -> str:
    canonical = json.dumps(
        {name: _canonical_value(name, getattr(form, name).data) for name in _FINGERPRINT_FIELDS},
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _canonical_value(field_name: str, value: Any) -> Any:
    if isinstance(value, str):
        return value if field_name in {'password', 'bearer_token'} else value.strip()
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)

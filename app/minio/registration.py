from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.minio.contracts import MinioRegistrationInput

_REGISTRATION_PROOF_SALT = 'minio-registration-proof-v1'
REGISTRATION_PROOF_MAX_AGE_SECONDS = 600
_FINGERPRINT_FIELDS = (
    'name',
    'environment',
    'description',
    'endpoint',
    'access_key',
    'secret_key',
    'region',
    'addressing_style',
    'timeout',
    'verify_ssl',
    'declared_release',
    'enabled',
)


def issue_registration_proof(*, values: MinioRegistrationInput, user_id: int) -> str:
    return _serializer().dumps({'user_id': int(user_id), 'fingerprint': _input_fingerprint(values)})


def verify_registration_proof(
    *,
    token: str | None,
    values: MinioRegistrationInput,
    user_id: int,
) -> tuple[bool, str]:
    if not token:
        return False, 'Run Test Connection before registering this MinIO provider.'
    try:
        payload = _serializer().loads(token, max_age=REGISTRATION_PROOF_MAX_AGE_SECONDS)
    except SignatureExpired:
        return False, 'The successful connection test expired. Run Test Connection again.'
    except BadSignature:
        return False, 'The connection test proof is invalid. Run Test Connection again.'
    if int(payload.get('user_id') or 0) != int(user_id):
        return False, 'The connection test belongs to another session. Run Test Connection again.'
    if not hmac.compare_digest(str(payload.get('fingerprint') or ''), _input_fingerprint(values)):
        return False, 'Connection settings changed after testing. Run Test Connection again.'
    return True, ''


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=current_app.config['SECRET_KEY'], salt=_REGISTRATION_PROOF_SALT)


def _input_fingerprint(values: MinioRegistrationInput) -> str:
    canonical = json.dumps(
        {name: _canonical_value(name, getattr(values, name)) for name in _FINGERPRINT_FIELDS},
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _canonical_value(field_name: str, value: Any) -> Any:
    if isinstance(value, str):
        return value if field_name == 'secret_key' else value.strip()
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)

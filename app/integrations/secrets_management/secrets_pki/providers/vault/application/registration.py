from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.integrations.secrets_management.secrets_pki.providers.vault.application.forms import VaultConnectionInput

_SALT = 'vault-registration-proof-v1'


def _fingerprint(values: VaultConnectionInput) -> str:
    # Only the SHA256 fingerprint is signed; never serialize credential material.
    return hashlib.sha256(
        json.dumps(asdict(values), sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=_SALT)


def issue_proof(values: VaultConnectionInput, user_id: int) -> str:
    return _serializer().dumps({'uid': int(user_id), 'fingerprint': _fingerprint(values)})


def verify_proof(proof: str, values: VaultConnectionInput, user_id: int) -> bool:
    if not proof:
        return False
    try:
        data = _serializer().loads(proof, max_age=600)
    except (BadSignature, SignatureExpired):
        return False
    return int(data.get('uid', 0)) == user_id and hmac.compare_digest(
        str(data.get('fingerprint') or ''), _fingerprint(values),
    )

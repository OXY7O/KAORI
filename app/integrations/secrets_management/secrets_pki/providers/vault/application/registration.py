from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.integrations.secrets_management.secrets_pki.providers.vault.application.forms import VaultConnectionInput
from app.security.credentials import decrypt_credential, encrypt_credential

_SALT = 'vault-registration-proof-v1'


def _fingerprint(values: VaultConnectionInput) -> str:
    # The encrypted SecretID is carried separately; never sign or expose plaintext.
    fields = asdict(values)
    fields.pop('secret_id')
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=_SALT)


def issue_proof(values: VaultConnectionInput, user_id: int) -> str:
    encrypted = encrypt_credential(values.secret_id)
    if not encrypted:
        raise ValueError('AppRole SecretID cannot be empty.')
    return _serializer().dumps(
        {
            'uid': int(user_id),
            'fingerprint': _fingerprint(values),
            'encrypted_secret_id': encrypted,
        }
    )


def verified_secret(proof: str, values: VaultConnectionInput, user_id: int) -> str | None:
    """Return the credential only after TTL, user and exact field verification."""
    if not proof:
        return None
    try:
        data = _serializer().loads(proof, max_age=600)
    except (BadSignature, SignatureExpired):
        return None
    if int(data.get('uid', 0)) != user_id or not hmac.compare_digest(
        str(data.get('fingerprint') or ''),
        _fingerprint(values),
    ):
        return None
    secret = decrypt_credential(str(data.get('encrypted_secret_id') or ''))
    if not secret or (values.secret_id and not hmac.compare_digest(values.secret_id, secret)):
        return None
    return secret

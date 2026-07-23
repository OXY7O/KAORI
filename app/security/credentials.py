from __future__ import annotations

import base64
import hashlib
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, has_app_context
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

_PREFIX = 'enc:v1:'


class CredentialEncryptionError(RuntimeError):
    """Raised when KAORI cannot encrypt or decrypt an integration credential."""


def _configured_secrets() -> tuple[str, ...]:
    if has_app_context():
        configured = str(current_app.config.get('INTEGRATION_CREDENTIAL_KEY') or '').strip()
        previous_raw = str(current_app.config.get('INTEGRATION_CREDENTIAL_PREVIOUS_KEYS') or '')
    else:
        configured = (os.getenv('INTEGRATION_CREDENTIAL_KEY') or '').strip()
        previous_raw = os.getenv('INTEGRATION_CREDENTIAL_PREVIOUS_KEYS') or ''

    if not configured:
        raise CredentialEncryptionError('INTEGRATION_CREDENTIAL_KEY is required for integration credentials.')
    current = configured
    previous = tuple(value.strip() for value in previous_raw.split(',') if value.strip())
    return tuple(dict.fromkeys((current, *previous)))


def _fernet_for(secret_value: str) -> Fernet:
    secret = secret_value.encode('utf-8')
    try:
        decoded = base64.urlsafe_b64decode(secret)
    except Exception:
        decoded = b''
    key = secret if len(decoded) == 32 else base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def _fernet() -> Fernet:
    return _fernet_for(_configured_secrets()[0])


def encrypt_credential(value: str | None) -> str | None:
    if value is None or value == '':
        return value
    if value.startswith(_PREFIX):
        return value
    token = _fernet().encrypt(value.encode('utf-8')).decode('ascii')
    return f'{_PREFIX}{token}'


def decrypt_credential(value: str | None) -> str | None:
    if value is None or value == '':
        return value
    if not value.startswith(_PREFIX):
        raise CredentialEncryptionError(
            'Stored integration credential is not encrypted with the canonical enc:v1 format. '
            'Run the integration-domain migration or restore a valid database backup.'
        )
    token = value[len(_PREFIX) :]
    last_error: InvalidToken | None = None
    for secret in _configured_secrets():
        try:
            return _fernet_for(secret).decrypt(token.encode('ascii')).decode('utf-8')
        except InvalidToken as exc:
            last_error = exc
    raise CredentialEncryptionError(
        'Integration credential cannot be decrypted with the configured current or previous keys.'
    ) from last_error


class EncryptedText(TypeDecorator[str]):
    """Transparent encrypted-at-rest text for integration credentials."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        return encrypt_credential(value)

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        return decrypt_credential(value)

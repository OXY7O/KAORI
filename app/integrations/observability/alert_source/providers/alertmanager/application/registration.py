from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.integrations.observability.alert_source.providers.alertmanager.application.forms import (
    AlertmanagerInstanceForm,
)

_REGISTRATION_PROOF_SALT = 'alertmanager-registration-proof-v1'
REGISTRATION_PROOF_MAX_AGE_SECONDS = 600


def issue_registration_proof(
    *,
    form: AlertmanagerInstanceForm,
    user_id: int,
) -> str:
    """Issue a short-lived proof for one successfully tested draft form.

    The token stores only a signed form fingerprint and user identity. It never
    contains raw credentials, endpoints, or other submitted values.
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
    form: AlertmanagerInstanceForm,
    user_id: int,
) -> tuple[bool, str]:
    """Verify that the same user tested the same form within the allowed age."""
    if not token:
        return False, 'Run Test Connection before registering this instance.'

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


def _form_fingerprint(form: AlertmanagerInstanceForm) -> str:
    canonical = json.dumps(
        asdict(form),
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

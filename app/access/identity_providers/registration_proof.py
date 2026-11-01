"""Short-lived, actor-bound Test Connection proof for new Identity Providers.

Matches the canonical Integration registration pattern. No credentials or
provider configuration values are embedded in the signed token.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.access.identity_providers.forms import IdentityProviderForm

_REGISTRATION_PROOF_SALT = 'identity-provider-registration-proof-v1'
REGISTRATION_PROOF_MAX_AGE_SECONDS = 600

# Include all fields which can influence persisted provider identity,
# authentication, projection or admission. Hidden inactive configuration
# fields are harmlessly included to invalidate a stale draft as they change.
_FINGERPRINT_FIELDS = (
    'key',
    'display_name',
    'provider_key',
    'enabled',
    'jit_enabled',
    'default_role_id',
    'admission_values',
    'server_uri',
    'base_dn',
    'bind_dn',
    'bind_password_env',
    'user_filter',
    'tls_mode',
    'username_attribute',
    'email_attribute',
    'display_name_attribute',
    'stable_id_attribute',
    'client_id',
    'client_secret_env',
)


def issue_registration_proof(*, form: IdentityProviderForm, user_id: int) -> str:
    return _serializer().dumps({'user_id': int(user_id), 'fingerprint': _form_fingerprint(form)})


def verify_registration_proof(*, token: str | None, form: IdentityProviderForm, user_id: int) -> tuple[bool, str]:
    if not token:
        return False, 'Run Test Connection before saving this identity provider.'
    try:
        payload = _serializer().loads(token, max_age=REGISTRATION_PROOF_MAX_AGE_SECONDS)
    except SignatureExpired:
        return False, 'The connection test expired. Run Test Connection again.'
    except BadSignature:
        return False, 'The connection test proof is invalid. Run Test Connection again.'
    if not isinstance(payload, dict):
        return False, 'The connection test proof is malformed. Run Test Connection again.'
    if int(payload.get('user_id') or 0) != int(user_id):
        return False, 'The connection test belongs to another user. Run Test Connection again.'
    if not hmac.compare_digest(str(payload.get('fingerprint') or ''), _form_fingerprint(form)):
        return False, 'Provider configuration changed after testing. Run Test Connection again.'
    return True, ''


def _form_fingerprint(form: IdentityProviderForm) -> str:
    canonical = json.dumps(
        {name: _canonical_value(getattr(form, name).data) for name in _FINGERPRINT_FIELDS},
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _canonical_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=_REGISTRATION_PROOF_SALT)

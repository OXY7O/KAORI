from __future__ import annotations

from typing import Any

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.auth.providers.ldap import ExternalIdentity

_PROJECTION_PROOF_SALT = 'ldap-directory-projection-proof-v1'
PROJECTION_PROOF_MAX_AGE_SECONDS = 600


class ProjectionProofError(ValueError):
    pass


def issue_projection_proof(*, provider_id: int, identity: ExternalIdentity, user_id: int) -> str:
    return _serializer().dumps(
        {
            'provider_id': int(provider_id),
            'user_id': int(user_id),
            'identity': {
                'subject': identity.subject,
                'username': identity.username,
                'email': identity.email,
                'display_name': identity.display_name,
                'distinguished_name': identity.distinguished_name,
            },
        }
    )


def verify_projection_proof(*, token: str, provider_id: int, user_id: int) -> ExternalIdentity:
    try:
        payload = _serializer().loads(token, max_age=PROJECTION_PROOF_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise ProjectionProofError('The directory identity proof expired. Search the LDAP directory again.') from exc
    except BadSignature as exc:
        raise ProjectionProofError('The directory identity proof is invalid. Search the LDAP directory again.') from exc

    if not isinstance(payload, dict):
        raise ProjectionProofError('The directory identity proof is malformed.')
    if int(payload.get('provider_id') or 0) != int(provider_id) or int(payload.get('user_id') or 0) != int(user_id):
        raise ProjectionProofError('The directory identity proof does not match this provisioning request.')

    identity = payload.get('identity')
    if not isinstance(identity, dict):
        raise ProjectionProofError('The directory identity proof does not contain an identity payload.')

    subject = _required_text(identity, 'subject')
    username = _required_text(identity, 'username')
    distinguished_name = _required_text(identity, 'distinguished_name')
    return ExternalIdentity(
        subject=subject,
        username=username,
        email=_optional_text(identity.get('email')),
        display_name=_optional_text(identity.get('display_name')),
        distinguished_name=distinguished_name,
    )


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or '').strip()
    if not value:
        raise ProjectionProofError(f'The directory identity proof is missing {key.replace("_", " ")}.')
    return value


def _optional_text(value: object) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=_PROJECTION_PROOF_SALT)

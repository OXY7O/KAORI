from __future__ import annotations

import hashlib
import hmac
import json

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_REGISTRATION_PROOF_SALT = 'kubernetes-cluster-registration-proof-v1'
REGISTRATION_PROOF_MAX_AGE_SECONDS = 600


def issue_cluster_registration_proof(
    *,
    user_id: int,
    name: str,
    environment: str,
    description: str | None,
    kubeconfig_content: str,
    verify_ssl: bool,
    allow_weak_tls: bool,
) -> str:
    return _serializer().dumps(
        {
            'user_id': int(user_id),
            'fingerprint': _fingerprint(
                name=name,
                environment=environment,
                description=description,
                kubeconfig_content=kubeconfig_content,
                verify_ssl=verify_ssl,
                allow_weak_tls=allow_weak_tls,
            ),
        }
    )


def verify_cluster_registration_proof(
    *,
    token: str | None,
    user_id: int,
    name: str,
    environment: str,
    description: str | None,
    kubeconfig_content: str,
    verify_ssl: bool,
    allow_weak_tls: bool,
) -> tuple[bool, str]:
    if not token:
        return False, 'Run Test Connection before saving this Kubernetes connection.'
    try:
        payload = _serializer().loads(token, max_age=REGISTRATION_PROOF_MAX_AGE_SECONDS)
    except SignatureExpired:
        return False, 'The successful connection test expired. Run Test Connection again.'
    except BadSignature:
        return False, 'The connection test proof is invalid. Run Test Connection again.'
    if int(payload.get('user_id') or 0) != int(user_id):
        return False, 'The connection test belongs to another session. Run Test Connection again.'
    expected = _fingerprint(
        name=name,
        environment=environment,
        description=description,
        kubeconfig_content=kubeconfig_content,
        verify_ssl=verify_ssl,
        allow_weak_tls=allow_weak_tls,
    )
    if not hmac.compare_digest(str(payload.get('fingerprint') or ''), expected):
        return False, 'Cluster settings changed after testing. Run Test Connection again.'
    return True, ''


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=current_app.config['SECRET_KEY'],
        salt=_REGISTRATION_PROOF_SALT,
    )


def _fingerprint(
    *,
    name: str,
    environment: str,
    description: str | None,
    kubeconfig_content: str,
    verify_ssl: bool,
    allow_weak_tls: bool,
) -> str:
    canonical = json.dumps(
        {
            'name': name.strip(),
            'environment': environment.strip(),
            'description': (description or '').strip(),
            'kubeconfig_sha256': hashlib.sha256(kubeconfig_content.encode('utf-8')).hexdigest(),
            'verify_ssl': bool(verify_ssl),
            'allow_weak_tls': bool(allow_weak_tls),
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

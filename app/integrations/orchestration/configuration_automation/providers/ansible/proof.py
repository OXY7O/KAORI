"""Timed user-bound immutable source validation proof, as in Harbor/Vault."""

from __future__ import annotations

import hashlib
import hmac
import json

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.integrations.orchestration.configuration_automation.providers.ansible.contract import (
    AnsibleConnectionInput,
)
from app.integrations.source_control.source_control.providers.github.public_automation_source import (
    PublicSourceEvidence,
)

_SALT = 'ansible-kubespray-source-proof-v1'
_MAX_AGE = 600


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=_SALT)


def _fingerprint(values: AnsibleConnectionInput) -> str:
    payload = json.dumps(values.fingerprint_fields(), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def issue_source_proof(values: AnsibleConnectionInput, evidence: PublicSourceEvidence, user_id: int) -> str:
    if evidence.revision != values.revision or evidence.repository != values.repository:
        raise ValueError('Source proof does not match the submitted Git identity.')
    return _serializer().dumps(
        {'uid': int(user_id), 'fingerprint': _fingerprint(values), 'evidence': evidence.as_dict()}
    )


def verified_source_proof(
    token: str, values: AnsibleConnectionInput, user_id: int
) -> dict[str, str | int | bool] | None:
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict) or payload.get('uid') != int(user_id):
        return None
    if not hmac.compare_digest(str(payload.get('fingerprint') or ''), _fingerprint(values)):
        return None
    evidence = payload.get('evidence')
    if (
        not isinstance(evidence, dict)
        or evidence.get('repository') != values.repository
        or evidence.get('revision') != values.revision
        or evidence.get('profile_key') != values.profile_key
        or evidence.get('status') != 'source_checked'
        or evidence.get('operation_authorized') is not False
        or evidence.get('checked_files') != 5
    ):
        return None
    return evidence

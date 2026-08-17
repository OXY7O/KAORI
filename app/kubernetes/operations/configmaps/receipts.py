from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_DELETE_RECEIPT_MAX_AGE_SECONDS = 600


@dataclass(frozen=True)
class ConfigMapDeleteReceipt:
    resource_version: str


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config['SECRET_KEY'],
        salt='kaori-configmap-delete-validation-v2',
    )


def issue_delete_receipt(metadata: dict[str, Any], *, user_id: int) -> str:
    return _serializer().dumps(
        {
            'user_id': int(user_id),
            'cluster_id': str(metadata['cluster_id']),
            'namespace': str(metadata['namespace']),
            'configmap_name': str(metadata['configmap_name']),
            'resource_version': str(metadata['resource_version']),
        }
    )


def verify_delete_receipt(
    token: str,
    *,
    user_id: int,
    cluster_id: str,
    namespace: str,
    configmap_name: str,
) -> ConfigMapDeleteReceipt:
    if not token.strip():
        raise ValueError('Validate the ConfigMap deletion before applying the final delete action.')
    try:
        payload = _serializer().loads(
            token,
            max_age=_DELETE_RECEIPT_MAX_AGE_SECONDS,
        )
    except SignatureExpired as exc:
        raise ValueError('The deletion validation expired. Run validation again before deleting.') from exc
    except BadSignature as exc:
        raise ValueError('The deletion validation receipt is invalid. Run validation again.') from exc

    try:
        receipt_user_id = int(payload.get('user_id'))
    except (TypeError, ValueError) as exc:
        raise ValueError('The deletion validation receipt is invalid. Run validation again.') from exc
    if receipt_user_id != int(user_id):
        raise ValueError('The deletion validation belongs to a different KAORI user. Run validation again.')

    expected = (
        str(payload.get('cluster_id') or ''),
        str(payload.get('namespace') or ''),
        str(payload.get('configmap_name') or ''),
    )
    selected = (cluster_id, namespace, configmap_name)
    if selected != expected:
        raise ValueError('The selected ConfigMap changed after validation. Run validation again.')

    resource_version = str(payload.get('resource_version') or '')
    if not resource_version:
        raise ValueError('The deletion validation receipt is incomplete. Run validation again.')
    return ConfigMapDeleteReceipt(resource_version=resource_version)

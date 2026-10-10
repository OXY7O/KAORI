"""Native provider execution identity via the registered KAORI kubeconfig (#1047).

KAORI app operator authorization is a distinct trust domain from the Kubernetes
client-certificate principal. Neither a manager label nor successful provider
authentication alone constitutes the independent human Release decision.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kubernetes.client import (
    V1ResourceAttributes,
    V1SelfSubjectAccessReview,
    V1SelfSubjectAccessReviewSpec,
    V1SelfSubjectReview,
)
from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.models import User

_REQUIRED_PERMISSIONS = ('tenant.manage', 'integrations.manage', 'clusters.manage')
_RESOURCES = {'Namespace': 'namespaces', 'ResourceQuota': 'resourcequotas', 'LimitRange': 'limitranges'}


def _field(record: Any, key: str, default: Any = None) -> Any:
    return record.get(key, default) if isinstance(record, Mapping) else getattr(record, key, default)


def require_platform_admin_actor(actor_user_id: int) -> None:
    """Use existing KAORI authorization; no duplicate Platform Admin role engine."""
    actor = db.session.get(User, actor_user_id)
    if actor is None or not all(
        callable(getattr(actor, 'has_permission', None)) and actor.has_permission(key)
        for key in _REQUIRED_PERMISSIONS
    ):
        raise ValueError('Platform Admin permissions are required for Native governance transfer.')


def verify_native_provider_admin_authority(
    *, cluster: Any, components: list[dict[str, Any]],
) -> dict[str, Any]:
    """SelfSubjectReview and named SelfSubjectAccessReviews using KAORI kubeconfig.

    Read-only provider requests; no uploaded cert/private key or impersonation.
    A group or label is NEVER treated as an independent approval receipt.
    """
    connection = _field(cluster, 'kubernetes_connection')
    if _field(connection, 'verify_ssl') is not True:
        raise ValueError('Verified Kubernetes TLS is required for Platform Admin authority.')
    if not isinstance(components, list) or not 0 < len(components) <= 100:
        raise ValueError('A bounded exact Native resource scope is required.')
    scope = []
    seen = set()
    for item in components:
        if not isinstance(item, Mapping):
            raise ValueError('Native provider authorization scope is malformed.')
        kind, name = item.get('kind'), item.get('name')
        namespace = item.get('namespace') or name
        key = (kind, namespace, name)
        if (
            kind not in _RESOURCES
            or not isinstance(name, str) or not name
            or not isinstance(namespace, str) or not namespace
            or not item.get('uid') or not item.get('resource_version')
            or kind == 'Namespace' and name != namespace
            or key in seen
        ):
            raise ValueError('Invalid or duplicated Native resource in provider authorization scope.')
        seen.add(key)
        scope.append({'kind': kind, 'name': name, 'namespace': namespace})
    provider = runtime_adapter.build_client(cluster)
    try:
        identity = provider.authentication_api().create_self_subject_review(
            body=V1SelfSubjectReview(), _request_timeout=5,
        )
    except ApiException:
        raise ValueError('Kubernetes SelfSubjectReview did not verify the configured kubeconfig.') from None
    user = _field(_field(identity, 'status'), 'user_info')
    username = _field(user, 'username')
    groups = _field(user, 'groups') or []
    if (
        not isinstance(username, str) or not username or username.startswith('system:serviceaccount:')
        or not isinstance(groups, (list, tuple))
        or not all(isinstance(group, str) and group for group in groups)
    ):
        raise ValueError('Kubernetes provider connection did not yield a trusted human admin principal.')
    extra = _field(user, 'extra') or {}
    credential_ids = _field(extra, 'authentication.kubernetes.io/credential-id', [])
    credential_id = (
        credential_ids[0]
        if isinstance(credential_ids, (tuple, list)) and len(credential_ids) == 1
        and isinstance(credential_ids[0], str)
        and credential_ids[0].startswith('X509SHA256=')
        else ''
    )
    for item in scope:
        for verb in ('get', 'patch'):
            resource = V1ResourceAttributes(
                group='', resource=_RESOURCES[item['kind']],
                name=item['name'], verb=verb,
                namespace=None if item['kind'] == 'Namespace' else item['namespace'],
            )
            review = V1SelfSubjectAccessReview(
                spec=V1SelfSubjectAccessReviewSpec(resource_attributes=resource),
            )
            try:
                response = provider.authorization_api().create_self_subject_access_review(
                    body=review, _request_timeout=5,
                )
            except ApiException:
                raise ValueError('Kubernetes SelfSubjectAccessReview could not verify provider permissions.') from None
            status = _field(response, 'status')
            if (
                _field(status, 'allowed') is not True
                or _field(status, 'denied') is True
                or _field(status, 'evaluation_error')
            ):
                raise ValueError(
                    f"KAORI Kubernetes connection lacks {verb} permission on {item['kind']}/{item['name']}."
                )
    return {
        'verification_source': 'kubernetes_self_subject_review',
        'authorization_source': 'kubernetes_self_subject_access_review',
        'provider_username': username,
        'provider_groups': list(groups),
        'provider_credential_id': credential_id,
        'cluster_id': str(_field(cluster, 'id') or ''),
        'scoped_resources': scope,
        'scope_count': len(scope),
        'resource_authority_verified': True,
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }

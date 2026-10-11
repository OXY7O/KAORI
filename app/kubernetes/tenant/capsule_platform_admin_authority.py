"""Read-only Capsule Platform Admin authority through the registered Kubernetes X.509 connection.

The Capsule Tenant CR is cluster-scoped; a Native Namespace SAR is not proof
of Capsule authority. Kubernetes remains authoritative for access decisions.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from kubernetes.client import (
    V1ResourceAttributes,
    V1SelfSubjectAccessReview,
    V1SelfSubjectAccessReviewSpec,
    V1SelfSubjectReview,
)
from kubernetes.client.rest import ApiException

from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.native_platform_admin_authority import _field

_CAPSULE_SHA256 = re.compile(r'[0-9a-f]{64}\Z')


def _capsule_admin_scope(components: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Validate the entire approved provider scope without inferring authority."""
    if not isinstance(components, list) or not 1 < len(components) <= 31:
        raise ValueError('A bounded Capsule Tenant and Namespace scope is required.')
    seen: set[tuple[str, str]] = set()
    scope: list[dict[str, str]] = []
    capsule_count = 0
    namespace_count = 0
    for item in components:
        if not isinstance(item, Mapping):
            raise ValueError('Capsule handoff provider scope is malformed.')
        kind, name = item.get('kind'), item.get('name')
        if (
            not isinstance(kind, str) or kind not in {'CapsuleTenant', 'Namespace'}
            or not isinstance(name, str) or not name.strip()
            or not isinstance(item.get('uid'), str) or not item['uid']
            or not isinstance(item.get('resource_version'), str) or not item['resource_version']
            or item.get('authority') != 'capsule'
            or item.get('handoff') not in {'external_acceptance_required', 'observe_only'}
            or (kind, name) in seen
        ):
            raise ValueError('Unknown, duplicate or incomplete Capsule handoff resource.')
        seen.add((kind, name))
        if kind == 'CapsuleTenant':
            capsule_count += 1
            if (
                item.get('handoff') != 'external_acceptance_required'
                or not isinstance(item.get('capsule_spec_sha256'), str)
                or not _CAPSULE_SHA256.fullmatch(item['capsule_spec_sha256'])
            ):
                raise ValueError('Capsule Tenant requires an exact provider spec and external handoff.')
        else:
            namespace_count += 1
            if item.get('namespace') != name:
                raise ValueError('Capsule Namespace handoff scope is inconsistent.')
        scope.append({
            'kind': kind,
            'name': name,
            'uid': item['uid'],
            'resource_version': item['resource_version'],
        })
    if capsule_count != 1 or namespace_count == 0:
        raise ValueError('Capsule handoff must include one Tenant CR and its governed Namespaces.')
    return scope


def verify_capsule_provider_admin_authority(
    *, cluster: Any, components: list[dict[str, Any]],
) -> dict[str, Any]:
    """Read-only SelfSubjectReview and exact-name get/patch SARs, no API mutation."""
    connection = _field(cluster, 'kubernetes_connection')
    if _field(connection, 'verify_ssl') is not True:
        raise ValueError('Verified Kubernetes TLS is required for Capsule Platform Admin authority.')
    scope = _capsule_admin_scope(components)
    provider = runtime_adapter.build_client(cluster)
    try:
        identity = provider.authentication_api().create_self_subject_review(
            body=V1SelfSubjectReview(), _request_timeout=5,
        )
    except (ApiException, AttributeError):
        raise ValueError('Kubernetes SelfSubjectReview could not verify Capsule provider identity.') from None
    user = _field(_field(identity, 'status'), 'user_info')
    username = _field(user, 'username')
    groups = _field(user, 'groups')
    extra = _field(user, 'extra') or {}
    identifiers = _field(extra, 'authentication.kubernetes.io/credential-id', [])
    credential_id = (
        identifiers[0]
        if isinstance(identifiers, (list, tuple)) and len(identifiers) == 1
        and isinstance(identifiers[0], str)
        and identifiers[0].startswith('X509SHA256=')
        and len(identifiers[0]) > len('X509SHA256=')
        else ''
    )
    if (
        not isinstance(username, str) or not username
        or username.startswith(('system:serviceaccount:', 'system:node:'))
        or not isinstance(groups, (list, tuple))
        or not all(isinstance(group, str) and group for group in groups)
        or not credential_id
    ):
        raise ValueError('A verified human X.509 Kubernetes principal is required for Capsule acceptance.')
    for item in scope:
        capsule = item['kind'] == 'CapsuleTenant'
        for verb in ('get', 'patch'):
            attributes = V1ResourceAttributes(
                group='capsule.clastix.io' if capsule else '',
                resource='tenants' if capsule else 'namespaces',
                name=item['name'],
                verb=verb,
                namespace=None,
            )
            review = V1SelfSubjectAccessReview(
                spec=V1SelfSubjectAccessReviewSpec(resource_attributes=attributes)
            )
            try:
                result = provider.authorization_api().create_self_subject_access_review(
                    body=review, _request_timeout=5,
                )
            except (ApiException, AttributeError):
                raise ValueError('Kubernetes SelfSubjectAccessReview failed for Capsule scope.') from None
            status = _field(result, 'status')
            if (
                _field(status, 'allowed') is not True
                or _field(status, 'denied') is True
                or _field(status, 'evaluation_error')
            ):
                raise ValueError(
                    f"Provider lacks {verb} authority for {item['kind']}/{item['name']}."
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

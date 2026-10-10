"""Read-only Kubernetes identity proof candidate for Native Release (#1047).

Not a successor-consent receipt, admission authority or provider mutation path.
A Kubernetes TokenReview proves an authenticated Kubernetes principal at a point
in time, *not* a KAORI-account mapping or authorization to execute Release.
The #690 identity/consent decision must be accepted separately before any
mutating #1048/#1049 workflow may consume this kind of evidence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from kubernetes.client import (
    V1ResourceAttributes,
    V1SubjectAccessReview,
    V1SubjectAccessReviewSpec,
    V1TokenReview,
    V1TokenReviewSpec,
)

from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.release_handoff_approval import _checked_recently, _plan_hash

# Successor labels are Kubernetes label VALUES, not unconstrained KAORI references.
_LABEL_VALUE = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,61}[A-Za-z0-9])?\Z')
_MAX_TOKEN_LENGTH = 16384


def _field(record: Any, key: str, default: Any = None) -> Any:
    return record.get(key, default) if isinstance(record, Mapping) else getattr(record, key, default)


def _verify_review_plan(plan: Mapping[str, Any], cluster_id: str) -> str:
    owner = str(plan.get('successor_owner') or '')
    digest = str(plan.get('plan_sha256') or '')
    if (
        plan.get('provider') != 'native_kubernetes'
        or plan.get('cluster_id') != cluster_id
        or not plan.get('tenant_id')
        or type(plan.get('generation')) is not int
        or plan['generation'] < 1
        or not isinstance(plan.get('handoff_components'), list)
        or not plan['handoff_components']
        or not isinstance(plan.get('provider_identity'), list)
        or not plan['provider_identity']
        or not plan.get('handoff_fingerprint')
        or not _checked_recently(plan.get('requested_at'))
        or len(digest) != 64
        or _plan_hash(dict(plan)) != digest
    ):
        raise ValueError('A fresh, exact Native handoff plan is required for identity review.')
    if (
        not _LABEL_VALUE.fullmatch(owner)
        or owner.lower() == 'kaori'
        or owner.startswith('system')
    ):
        raise ValueError('The successor must use a valid non-system Kubernetes owner label.')
    return owner


def verify_native_successor_identity_for_review(
    *, cluster: Any, plan: Mapping[str, Any], provider_token: str,
) -> dict[str, Any]:
    """Authenticate the prospective successor through the *cluster* API server.

    No token, bearer, Kubernetes response credential or unverified consent is
    committed. The returned evidence cannot on its own authorize live handoff.
    The caller must supply a token via an independently approved secure channel;
    no HTTP form, credential storage or broad provider privileges are added here.
    """
    connection = _field(cluster, 'kubernetes_connection')
    if _field(connection, 'verify_ssl') is not True:
        raise ValueError('Kubernetes TLS verification is required for identity review.')
    cluster_id = str(_field(cluster, 'id') or '')
    owner = _verify_review_plan(plan, cluster_id)
    if (
        not isinstance(provider_token, str)
        or not provider_token
        or len(provider_token) > _MAX_TOKEN_LENGTH
        or any(c.isspace() for c in provider_token)
    ):
        raise ValueError('A bounded Kubernetes authentication token is required.')
    # The canonical cluster kubeconfig identifies the API server. TokenReview
    # authenticates the separately supplied successor token against that server.
    provider = runtime_adapter.build_client(cluster)
    reply = provider.authentication_api().create_token_review(
        V1TokenReview(spec=V1TokenReviewSpec(token=provider_token)),
        _request_timeout=5,
    )
    status = _field(reply, 'status')
    principal = _field(status, 'user')
    username = str(_field(principal, 'username') or '')
    principal_uid = str(_field(principal, 'uid') or '')
    groups = _field(principal, 'groups') or []
    audiences = _field(status, 'audiences') or []
    if (
        _field(status, 'authenticated') is not True
        or _field(status, 'error')
        or not username
        or not principal_uid
        or username.startswith('system:')
        or not isinstance(groups, (list, tuple))
        or not all(isinstance(group, str) for group in groups)
        or owner not in groups
        or any(group == 'system:masters' for group in groups)
    ):
        raise ValueError('Kubernetes did not authenticate an eligible successor group member.')
    return {
        'status': 'provider_identity_observed_consent_unverified',
        'verification_source': 'kubernetes_token_review',
        'cluster_id': cluster_id,
        'tenant_id': plan['tenant_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'successor_owner': owner,
        'provider_username': username,
        'provider_principal_uid': principal_uid,
        'provider_groups_include_successor': True,
        'audience_reported': bool(audiences),
        'checked_at': datetime.now(UTC).isoformat(),
        'consent_verified': False,
        'identity_mapping_admitted': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }


def verify_native_successor_resource_authority(
    *, cluster: Any, plan: Mapping[str, Any], provider_token: str,
    ownership_required: str = 'kaori_marker_correlated',
) -> dict[str, Any]:
    """TokenReview plus SubjectAccessReview against EACH exact scoped Native object.

    The submitted bearer is kept only in call memory; external Kubernetes is
    authoritative for both authentication and actual RBAC. SubjectAccessReview
    is never interpreted as consent without a separate explicit declaration.
    """
    proof = verify_native_successor_identity_for_review(
        cluster=cluster, plan=plan, provider_token=provider_token,
    )
    # The original plan is immutable; fail closed on inconsistent resource
    # scope rather than inferring wildcard RBAC or selecting new objects.
    items = plan.get('handoff_components')
    if not isinstance(items, list) or not 0 < len(items) <= 100:
        raise ValueError('Native successor authorization scope is incomplete.')
    if ownership_required not in {'kaori_marker_correlated', 'external_successor_correlated'}:
        raise ValueError('Unsupported Native ownership authorization boundary.')
    selected = [item for item in items if item.get('handoff') == 'external_acceptance_required']
    if not selected:
        raise ValueError('No KAORI-correlated Native resources are approved for transfer.')
    identities: set[tuple[str, str, str]] = set()
    scope: list[dict[str, str]] = []
    for item in selected:
        kind = item.get('kind')
        name = item.get('name')
        namespace = item.get('namespace') or name
        if (
            kind not in ('Namespace', 'ResourceQuota', 'LimitRange')
            or not isinstance(name, str) or not name
            or not isinstance(namespace, str) or not namespace
            or not item.get('uid') or not item.get('resource_version')
            or item.get('ownership') != ownership_required
            or (kind == 'Namespace' and name != namespace)
        ):
            raise ValueError('Native successor authorization scope is malformed.')
        key = (namespace, kind, name)
        if key in identities:
            raise ValueError('Duplicated provider resource in successor authorization scope.')
        identities.add(key)
        scope.append({'namespace': namespace, 'kind': kind, 'name': name})
    # A direct TokenReview must be used again in the same execution request
    # rather than relying solely on these recorded SAR results.
    provider = runtime_adapter.build_client(cluster)
    # Only scoped resource permissions. No cluster administrator assumption and
    # no automatic Kubernetes RoleBinding/ClusterRoleBinding provisioning.
    resources = {
        'Namespace': 'namespaces',
        'ResourceQuota': 'resourcequotas',
        'LimitRange': 'limitranges',
    }
    for entry in scope:
        for verb in ('get', 'patch'):
            attrs = V1ResourceAttributes(
                group='', resource=resources[entry['kind']],
                name=entry['name'], verb=verb,
                namespace=None if entry['kind'] == 'Namespace' else entry['namespace'],
            )
            req = V1SubjectAccessReview(
                spec=V1SubjectAccessReviewSpec(
                    user=proof['provider_username'],
                    uid=proof['provider_principal_uid'],
                    groups=[proof['successor_owner']],
                    resource_attributes=attrs,
                ),
            )
            result = provider.authorization_api().create_subject_access_review(
                req, _request_timeout=5,
            )
            status = _field(result, 'status')
            if (
                _field(status, 'allowed') is not True
                or _field(status, 'denied') is True
                or _field(status, 'evaluation_error')
            ):
                raise ValueError(
                    f"Successor lacks verified Kubernetes {verb} authorization for "
                    f"{entry['kind']}/{entry['name']}."
                )
    return {
        **proof,
        'status': 'provider_identity_and_rbac_verified_consent_unverified',
        'scoped_resources': scope,
        'scope_count': len(scope),
        'rbac_checked_verbs': ['get', 'patch'],
        'resource_authority_verified': True,
        'consent_verified': False,
        'release_authorized': False,
    }

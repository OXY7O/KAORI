from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.capsule_provider import discover_capsule
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant

_GROUP = 'capsule.clastix.io'
_PLURAL = 'tenants'
_TARGET = 'kubernetes_tenant_external_access_inventory'
_MAX_BINDINGS = 200


def _subject(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError('External Capsule subject evidence is malformed.')
    kind = str(value.get('kind') or 'Unknown')
    name = str(value.get('name') or '')
    namespace = str(value.get('namespace') or '')
    if len(name) > 253 or len(namespace) > 253:
        raise ValueError('External Capsule subject identity is invalid.')
    return {'kind': kind, 'name': name, 'namespace': namespace}


def normalize_capsule_access_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Summarize provider-owned RBAC without creating KAORI Membership/Grants."""
    owners = spec.get('owners') or []
    additional = spec.get('additionalRoleBindings') or []
    rules = spec.get('rules') or []
    if not all(isinstance(v, list) for v in (owners, additional, rules)):
        raise ValueError('Capsule access contract has unsupported owners/rules/bindings structure.')
    if len(owners) + len(additional) + len(rules) > _MAX_BINDINGS:
        raise ValueError('Capsule access observation exceeds bounded evidence limit.')

    observed_owners = [_subject(owner) for owner in owners]
    bindings: list[dict[str, Any]] = []

    def capture(entry: Any, *, source: str, selector: Any = None) -> None:
        if not isinstance(entry, dict):
            raise ValueError('Capsule access binding structure is unsupported.')
        labels = entry.get('labels') or {}
        subjects = entry.get('subjects') or []
        if not isinstance(labels, dict) or not isinstance(subjects, list):
            raise ValueError('Capsule access binding ownership/principal structure is unsupported.')
        if len(bindings) + 1 > _MAX_BINDINGS:
            raise ValueError('Capsule access binding evidence is unbounded.')
        managed = labels.get('app.kubernetes.io/managed-by') == 'kaori'
        grant_id = str(labels.get('kaori.io/access-grant') or '')
        bindings.append({
            'source': source,
            'cluster_role_name': str(entry.get('clusterRoleName') or ''),
            'subjects': [_subject(subject) for subject in subjects],
            'scope_selector': selector,
            'ownership': 'kaori' if managed and grant_id else 'external',
            'kaori_grant_id': grant_id if managed and grant_id else None,
            'governance': 'committed_grant_candidate' if managed and grant_id else 'observed_review_required',
        })

    for binding in additional:
        capture(binding, source='additionalRoleBindings')
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError('Capsule RBAC rule structure is malformed.')
        permissions = rule.get('permissions') or {}
        if not isinstance(permissions, dict):
            raise ValueError('Capsule RBAC permissions are malformed.')
        rule_bindings = permissions.get('bindings') or []
        if not isinstance(rule_bindings, list):
            raise ValueError('Capsule RBAC bindings are malformed.')
        selector = rule.get('namespaceSelector') or {}
        if not isinstance(selector, dict):
            raise ValueError('Capsule Namespace selector is malformed.')
        for binding in rule_bindings:
            capture(binding, source='rules.permissions.bindings', selector=selector)
    return {
        'owners': observed_owners,
        'bindings': bindings,
        'external_count': sum(item['ownership'] == 'external' for item in bindings),
        'kaori_count': sum(item['ownership'] == 'kaori' for item in bindings),
        'owner_count': len(observed_owners),
        'status': 'review_required' if owners or any(x['ownership'] == 'external' for x in bindings) else 'observed',
    }


def latest_external_capsule_access_evidence(tenant_id: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc())
        .first()
    )
    return dict(event.metadata_json or {}) if event else None


def observe_external_capsule_access_committed(*, tenant_id: str, actor_user_id: int) -> dict[str, Any]:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None or tenant.provider_key != 'capsule' or tenant.reconciliation_authority != 'capsule':
        raise ValueError('Select a governed Capsule Tenant with provider authority.')
    if tenant.lifecycle_status != 'ready' or tenant.provider_state != 'capsule':
        raise ValueError('Capsule authority is not healthy; external access observation is unavailable.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None or not tenant.provider_reference:
        raise ValueError('Capsule Tenant has no registered cluster/provider reference.')

    client = runtime_adapter.build_client(cluster)
    snapshot = discover_capsule(client.custom_objects_api().api_client)
    if 'v1beta2' not in snapshot.tenant_api_versions:
        raise ValueError('External Capsule access inventory requires served v1beta2 API.')
    item = client.custom_objects_api().get_cluster_custom_object(
        _GROUP, 'v1beta2', _PLURAL, str(tenant.provider_reference), _request_timeout=5
    )
    if not isinstance(item, dict) or not isinstance(item.get('spec'), dict):
        raise ValueError('Capsule Tenant access payload is invalid.')
    metadata = item.get('metadata') or {}
    source_uid = str(metadata.get('uid') or '')
    resource_version = str(metadata.get('resourceVersion') or '')
    expected_uid = str((tenant.provider_evidence_json or {}).get('provider_uid') or '')
    if not source_uid or not resource_version or (expected_uid and source_uid != expected_uid):
        raise ValueError('Capsule Tenant provider identity changed; re-adoption review is required.')
    result = normalize_capsule_access_spec(item['spec'])
    evidence = {
        'status': result['status'],
        'tenant_id': tenant.id,
        'cluster_id': tenant.cluster_id,
        'provider': 'capsule',
        'provider_uid': source_uid,
        'resource_version': resource_version,
        'observed_at': datetime.now(UTC).isoformat(),
        'external_count': result['external_count'],
        'kaori_count': result['kaori_count'],
        'owner_count': result['owner_count'],
        'owners': result['owners'],
        'bindings': result['bindings'],
        'identity_import_performed': False,
        'rbac_mutation_performed': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id,
        target_type=_TARGET,
        target_id=tenant.id,
        action='tenant.external_access.observed',
        summary='Observed Capsule-owned access without changing memberships or provider RBAC.',
        metadata_json=evidence,
    ))
    db.session.commit()
    return evidence

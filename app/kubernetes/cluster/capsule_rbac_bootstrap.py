from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from kubernetes.client import V1ClusterRole, V1ObjectMeta, V1PolicyRule
from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.access import (
    LATEST_ACCESS_PROFILE_VERSION,
    capsule_cluster_role_manifest,
    capsule_cluster_role_name,
    get_access_profile,
)
from app.kubernetes.tenant.capsule_provider import discover_capsule
from app.models.audit import AuditEvent
from app.models.kubernetes import KubernetesConnection

_TARGET = 'kubernetes_cluster_capsule_rbac_bootstrap'
_MANAGED_BY = 'app.kubernetes.io/managed-by'
_PROFILE = 'kaori.io/access-profile'
_PROFILE_VERSION = 'kaori.io/access-profile-version'


def _catalog() -> list[Any]:
    order = ('viewer', 'operator', 'tenant_admin', 'deployer')
    return [get_access_profile(key, LATEST_ACCESS_PROFILE_VERSION[key]) for key in order]


def _normalized(rules: Any) -> list[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]]:
    result = []
    for rule in rules or []:
        value = rule if isinstance(rule, dict) else rule.to_dict()
        if any(value.get(field) for field in ('resourceNames', 'resource_names', 'nonResourceURLs', 'non_resource_urls')):
            raise ValueError('Existing ClusterRole uses unsupported resource-name or non-resource restrictions.')
        result.append((
            tuple(sorted(value.get('apiGroups', value.get('api_groups')) or [])),
            tuple(sorted(value.get('resources') or [])),
            tuple(sorted(value.get('verbs') or [])),
        ))
    return sorted(result)


def _role_status(api: Any, profile: Any) -> dict[str, Any]:
    desired = capsule_cluster_role_manifest(profile)
    name = capsule_cluster_role_name(profile)
    fingerprint = hashlib.sha256(json.dumps(desired['rules'], sort_keys=True).encode()).hexdigest()
    row: dict[str, Any] = {
        'name': name,
        'profile': profile.label,
        'version': profile.version,
        'status': 'missing',
        'permissions_sha256': fingerprint,
        'uid': None,
        'resource_version': None,
    }
    try:
        existing = api.read_cluster_role(name, _request_timeout=5)
    except ApiException as exc:
        if exc.status == 404:
            return row
        raise
    meta = existing.metadata
    row['uid'] = str(meta.uid) if meta and meta.uid else None
    row['resource_version'] = str(meta.resource_version) if meta and meta.resource_version else None
    try:
        if getattr(existing, 'aggregation_rule', None) is not None:
            row['status'] = 'conflict'
            row['reason'] = 'Aggregated ClusterRoles cannot satisfy a fixed KAORI profile.'
        elif _normalized(existing.rules) == _normalized(desired['rules']):
            row['status'] = 'ready'
        else:
            row['status'] = 'conflict'
            row['reason'] = 'Existing ClusterRole does not match canonical profile permissions.'
    except ValueError as exc:
        row['status'] = 'conflict'
        row['reason'] = str(exc)
    return row


def _connection(cluster_id: str) -> KubernetesConnection:
    connection = KubernetesConnection.query.filter_by(cluster_id=cluster_id).first()
    if connection is None or connection.cluster is None or not connection.kubeconfig:
        raise ValueError('The Kubernetes cluster has no usable canonical integration connection.')
    return connection


def _read_roles(cluster_id: str) -> tuple[Any, list[dict[str, Any]]]:
    connection = _connection(cluster_id)
    client = runtime_adapter.build_client(connection)
    capsule = discover_capsule(client.custom_objects_api().api_client)
    if not capsule.installed or 'v1beta2' not in capsule.tenant_api_versions:
        raise ValueError('Healthy Capsule v1beta2 Tenant CRD discovery is required before RBAC bootstrap.')
    api = client.rbac_authorization_api()
    rows = [_role_status(api, profile) for profile in _catalog()]
    return api, rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'roles': rows,
        'ready': sum(row['status'] == 'ready' for row in rows),
        'missing': sum(row['status'] == 'missing' for row in rows),
        'conflict': sum(row['status'] == 'conflict' for row in rows),
        'checked_at': datetime.now(UTC).isoformat(),
    }


def _audit(
    cluster_id: str,
    actor_user_id: int,
    action: str,
    status: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        target_type=_TARGET,
        target_id=cluster_id,
        action=f'kubernetes_capsule_rbac_{action}_{status}',
        summary=f'Capsule ClusterRole {action}: {status}.',
        metadata_json={
            'operation': action,
            'status': status,
            'cluster_id': cluster_id,
            'source': 'versioned_kaori_access_profile_catalog',
            'secret_material_persisted': False,
            **data,
        },
    )
    db.session.add(event)
    db.session.commit()
    return dict(event.metadata_json or {})


def latest_capsule_role_bootstrap_evidence(cluster_id: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=cluster_id)
        .order_by(AuditEvent.id.desc())
        .first()
    )
    return dict(event.metadata_json or {}) if event else None


def check_capsule_role_bootstrap(cluster_id: str, actor_user_id: int) -> dict[str, Any]:
    try:
        _, rows = _read_roles(cluster_id)
    except (ApiException, ValueError) as exc:
        return _audit(cluster_id, actor_user_id, 'check', 'failed', {'error': type(exc).__name__})
    state = _summary(rows)
    status = 'conflict' if state['conflict'] else 'ready' if not state['missing'] else 'missing'
    return _audit(cluster_id, actor_user_id, 'check', status, state)


def _body(profile: Any) -> V1ClusterRole:
    manifest = capsule_cluster_role_manifest(profile)
    name = capsule_cluster_role_name(profile)
    return V1ClusterRole(
        metadata=V1ObjectMeta(
            name=name,
            labels={
                _MANAGED_BY: 'kaori',
                _PROFILE: profile.key.value,
                _PROFILE_VERSION: str(profile.version),
            },
        ),
        rules=[
            V1PolicyRule(api_groups=rule['apiGroups'], resources=rule['resources'], verbs=rule['verbs'])
            for rule in manifest['rules']
        ],
    )


def bootstrap_missing_capsule_roles(
    cluster_id: str, actor_user_id: int, *, approved: bool
) -> dict[str, Any]:
    if not approved:
        raise ValueError('Explicit cluster-scoped RBAC approval is required.')
    created: list[str] = []
    try:
        last_check = latest_capsule_role_bootstrap_evidence(cluster_id)
        if not last_check or last_check.get('operation') != 'check' or last_check.get('status') != 'missing':
            raise ValueError('A prior Check RBAC with missing roles is required before bootstrap.')
        checked_at = datetime.fromisoformat(str(last_check.get('checked_at') or ''))
        if checked_at.tzinfo is None or (datetime.now(UTC) - checked_at).total_seconds() > 900:
            raise ValueError('RBAC check evidence is stale; rerun Check RBAC before bootstrap.')
        api, rows = _read_roles(cluster_id)
        if any(row['status'] == 'conflict' for row in rows):
            raise ValueError('ClusterRole conflict detected; no existing role may be overwritten.')
        # Persist explicit authorization before mutating cluster-scoped RBAC.
        _audit(cluster_id, actor_user_id, 'bootstrap', 'started', _summary(rows))
        # Verify every missing role can be admitted before performing any mutation.
        for profile, row in zip(_catalog(), rows, strict=True):
            if row['status'] == 'missing':
                api.create_cluster_role(body=_body(profile), dry_run='All', _request_timeout=5)
        for profile, row in zip(_catalog(), rows, strict=True):
            if row['status'] != 'missing':
                continue
            api.create_cluster_role(body=_body(profile), _request_timeout=5)
            created.append(row['name'])
            verified = _role_status(api, profile)
            if verified['status'] != 'ready' or not verified['uid']:
                raise ValueError(f'ClusterRole {row["name"]} could not be verified after creation.')
        _, verified_rows = _read_roles(cluster_id)
        state = _summary(verified_rows)
        if state['missing'] or state['conflict']:
            raise ValueError('Post-bootstrap cluster RBAC verification is incomplete.')
        return _audit(cluster_id, actor_user_id, 'bootstrap', 'ready', {**state, 'created': created})
    except (ApiException, ValueError) as exc:
        # Preserve partial side effects and never report success for an incomplete bootstrap.
        try:
            observed = _summary(_read_roles(cluster_id)[1])
        except (ApiException, ValueError):
            observed = {}
        return _audit(
            cluster_id, actor_user_id, 'bootstrap', 'failed',
            {
                **observed, 'created': created, 'error': type(exc).__name__,
                'reason': str(exc)[:240] if isinstance(exc, ValueError) else 'Kubernetes API rejected RBAC mutation.',
                'partial': bool(created),
            },
        )

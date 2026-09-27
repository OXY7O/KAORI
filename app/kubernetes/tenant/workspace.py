from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from app.common.presentation import present_user_datetime
from app.intelligence.service import get_active_recommendation_findings
from app.kubernetes.tenant.capacity_governance import build_capacity_governance_summary
from app.kubernetes.tenant.credential import build_namespace_access_package, credential_target_namespaces
from app.kubernetes.tenant.job_adapter import build_tenant_sync_state
from app.models import Cluster
from app.models.tenant import (
    Tenant,
    TenantAccessGrant,
    TenantCredential,
    TenantEnvironment,
    TenantNamespace,
)
from app.models.tenant_advanced import TenantAdvancedCapabilityIntent
from app.models.tenant_audit import TenantAuditEvidence
from app.models.tenant_managed_resource import TenantManagedResourceIntent
from app.models.tenant_policy import TenantDomainReservation, TenantExposurePolicy


def _recent(model, *, limit: int) -> list[Any]:
    return model.query.order_by(model.id.desc()).limit(limit).all()


def _capacity_tone(state: str) -> str:
    if state == 'Healthy':
        return 'normal'
    if state == 'Near Capacity':
        return 'warning'
    if state in {'Critical', 'Exhausted', 'Overcommitted'}:
        return 'critical'
    return 'unknown'


def _provider_tone(state: str) -> str:
    if state == 'connected':
        return 'normal'
    if state == 'failed':
        return 'critical'
    return 'unknown'


def _cluster_tenant_counts() -> dict[str, int]:
    return {
        str(cluster_id): int(count)
        for cluster_id, count in (
            Tenant.query.with_entities(Tenant.cluster_id, func.count(Tenant.id)).group_by(Tenant.cluster_id).all()
        )
    }


def _cluster_namespace_counts() -> dict[str, int]:
    return {
        str(cluster_id): int(count)
        for cluster_id, count in (
            TenantNamespace.query.join(
                TenantEnvironment,
                TenantNamespace.tenant_environment_id == TenantEnvironment.id,
            )
            .join(Tenant, TenantEnvironment.tenant_id == Tenant.id)
            .with_entities(Tenant.cluster_id, func.count(TenantNamespace.id))
            .group_by(Tenant.cluster_id)
            .all()
        )
    }


def _snapshot_cluster_rows(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = snapshot.get('clusters')
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get('cluster_id')): row
        for row in rows
        if isinstance(row, dict) and str(row.get('cluster_id') or '').strip()
    }


def _tenant_collection_snapshot(sync_state: dict[str, Any]) -> dict[str, Any]:
    snapshot = dict(sync_state.get('snapshot') or {})
    namespace_count = int(snapshot.get('namespace_count') or 0)
    covered_count = int(snapshot.get('covered_namespace_count') or 0)
    exception_count = int(snapshot.get('exception_count') or 0)
    if sync_state['last_success_at'] is None:
        coverage_label = 'Not Collected'
        coverage_supporting = 'Run Tenant sync to establish committed coverage.'
        coverage_tone = 'warning'
        exception_label = 'Not Collected'
        exceptions_tone = 'warning'
    elif namespace_count:
        coverage_label = f'{covered_count} / {namespace_count} Namespaces'
        coverage_supporting = 'Fully committed' if covered_count == namespace_count else 'Coverage requires review'
        coverage_tone = 'normal' if covered_count == namespace_count else 'warning'
        exception_label = 'No Exceptions' if exception_count == 0 else f'{exception_count} Exceptions'
        exceptions_tone = 'normal' if exception_count == 0 else 'warning'
    else:
        coverage_label = '0 Namespaces'
        coverage_supporting = 'No governed Tenant namespaces were present in the snapshot.'
        coverage_tone = 'normal'
        exception_label = 'No Exceptions' if exception_count == 0 else f'{exception_count} Exceptions'
        exceptions_tone = 'normal' if exception_count == 0 else 'warning'

    return {
        'status': sync_state['label'],
        'tone': sync_state['tone'],
        'icon': sync_state['icon'],
        'description': sync_state['helper'],
        'last_sync_label': sync_state['last_success_label'],
        'scope_label': str(snapshot.get('scope_label') or 'All Clusters'),
        'coverage_label': coverage_label,
        'coverage_supporting': coverage_supporting,
        'coverage_tone': coverage_tone,
        'exception_count': exception_count,
        'exception_label': exception_label,
        'exceptions_tone': exceptions_tone,
        'source_label': str(snapshot.get('source') or 'KAORI Tenant State + committed Kubernetes Inventory'),
        'source_cutoff_label': present_user_datetime(
            snapshot.get('source_inventory_cutoff'),
            empty='No committed Kubernetes inventory cutoff',
        ),
        'automatic_enabled': sync_state['automatic_enabled'],
        'automatic_label': 'Enabled' if sync_state['automatic_enabled'] else 'Manual Only',
        'interval_label': sync_state['interval_label'],
        'next_run_label': sync_state['next_run_label'],
        'active_job': sync_state['active_job'],
        'latest_job': sync_state['latest_job'],
        'progress_percent': sync_state['progress_percent'],
        'progress_message': sync_state['progress_message'],
    }


def _attention_tone(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {'critical', 'high', 'failed', 'expired'}:
        return 'critical'
    if normalized in {'warning', 'medium', 'drifted', 'pending', 'renewal_due', 'suspended', 'rotating'}:
        return 'warning'
    return 'info'


def _tenant_attention_rows(findings: list[dict[str, Any]], *, limit: int = 6) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for finding in findings:
        severity = str(finding.get('severity') or 'warning')
        rows.append(
            {
                'kind': 'Governance',
                'icon': 'shield-alert',
                'title': str(finding.get('title') or finding.get('rule_key') or 'Tenant governance finding'),
                'detail': str(
                    finding.get('summary')
                    or finding.get('recommendation')
                    or finding.get('description')
                    or 'Review the canonical Tenant Governance finding.'
                ),
                'status': severity.title(),
                'tone': _attention_tone(severity),
            }
        )

    grants = (
        TenantAccessGrant.query.filter(
            TenantAccessGrant.status == 'active',
            TenantAccessGrant.reconciliation_status.in_(('pending', 'drifted', 'failed')),
        )
        .order_by(TenantAccessGrant.updated_at.desc())
        .limit(limit)
        .all()
    )
    for grant in grants:
        rows.append(
            {
                'kind': 'Access',
                'icon': 'key-round',
                'title': f'{grant.membership.subject_name} · {grant.access_profile.replace("_", " ").title()}',
                'detail': grant.reconciliation_message
                or f'{grant.tenant.name} access requires reconciliation review.',
                'status': grant.reconciliation_status.title(),
                'tone': _attention_tone(grant.reconciliation_status),
            }
        )

    credentials = (
        TenantCredential.query.filter(
            (
                TenantCredential.status.in_(('renewal_due', 'rotating', 'suspended', 'expired'))
                | TenantCredential.reconciliation_status.in_(('pending', 'drifted', 'failed'))
            )
        )
        .order_by(TenantCredential.updated_at.desc())
        .limit(limit)
        .all()
    )
    for credential in credentials:
        status = (
            credential.status
            if credential.status in {'renewal_due', 'rotating', 'suspended', 'expired'}
            else credential.reconciliation_status
        )
        rows.append(
            {
                'kind': 'Credential',
                'icon': 'key-square',
                'title': credential.service_account_name,
                'detail': f'{credential.tenant.name} · {credential.credential_type.replace("_", " ").title()}',
                'status': status.replace('_', ' ').title(),
                'tone': _attention_tone(status),
            }
        )

    tone_order = {'critical': 0, 'warning': 1, 'info': 2}
    rows.sort(key=lambda row: (tone_order.get(row['tone'], 3), row['kind'], row['title']))
    return rows[:limit]


def _sort_time(value: datetime | None) -> float:
    if value is None:
        return 0.0
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.timestamp()


def _tenant_recent_activity(*, limit: int = 6) -> list[dict[str, str]]:
    rows: list[tuple[datetime | None, dict[str, str]]] = []

    for tenant in Tenant.query.order_by(Tenant.updated_at.desc()).limit(limit).all():
        rows.append(
            (
                tenant.updated_at,
                {
                    'icon': 'building-2',
                    'title': tenant.name,
                    'detail': f'Tenant state · {tenant.lifecycle_status.replace("_", " ").title()} · {tenant.provider_state.replace("_", " ").title()}',
                    'time': present_user_datetime(tenant.updated_at, empty='Not recorded'),
                },
            )
        )

    for grant in TenantAccessGrant.query.order_by(TenantAccessGrant.updated_at.desc()).limit(limit).all():
        rows.append(
            (
                grant.updated_at,
                {
                    'icon': 'key-round',
                    'title': f'Access · {grant.membership.subject_name}',
                    'detail': f'{grant.tenant.name} · {grant.access_profile.replace("_", " ").title()} · {grant.status.title()}',
                    'time': present_user_datetime(grant.updated_at, empty='Not recorded'),
                },
            )
        )

    for credential in TenantCredential.query.order_by(TenantCredential.updated_at.desc()).limit(limit).all():
        rows.append(
            (
                credential.updated_at,
                {
                    'icon': 'key-square',
                    'title': credential.service_account_name,
                    'detail': f'{credential.tenant.name} · Credential {credential.status.replace("_", " ").title()}',
                    'time': present_user_datetime(credential.updated_at, empty='Not recorded'),
                },
            )
        )

    rows.sort(key=lambda item: _sort_time(item[0]), reverse=True)
    return [row for _updated_at, row in rows[:limit]]


def get_tenant_overview_context() -> dict[str, Any]:
    """Compose Overview-only cross-cluster posture from committed KAORI evidence."""

    clusters = Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).all()
    tenant_counts = _cluster_tenant_counts()
    namespace_counts = _cluster_namespace_counts()
    total_tenants = sum(tenant_counts.values())
    sync_state = build_tenant_sync_state()
    snapshot_clusters = _snapshot_cluster_rows(dict(sync_state.get('snapshot') or {}))

    cluster_rows: list[dict[str, Any]] = []
    for cluster in clusters:
        cluster_id = str(cluster.id)
        tenant_count = tenant_counts.get(cluster_id, 0)
        capacity = build_capacity_governance_summary(cluster.id)
        snapshot_cluster = snapshot_clusters.get(cluster_id, {})
        capacity_available = capacity.get('budget') is not None and capacity.get('headroom') is not None
        cluster_rows.append(
            {
                'id': cluster_id,
                'name': cluster.name,
                'environment': cluster.environment,
                'provider_status': cluster.status,
                'provider_tone': _provider_tone(cluster.status),
                'tenant_count': tenant_count,
                'namespace_count': namespace_counts.get(cluster_id, 0),
                'tenant_share_percent': round((tenant_count / total_tenants) * 100) if total_tenants else 0,
                'snapshot_coverage_complete': bool(snapshot_cluster.get('coverage_complete')),
                'snapshot_coverage_label': (
                    f"{int(snapshot_cluster.get('covered_namespace_count') or 0)} / "
                    f"{int(snapshot_cluster.get('namespace_count') or 0)} Namespaces"
                    if snapshot_cluster
                    else 'Not Collected'
                ),
                'snapshot_cutoff_label': present_user_datetime(
                    snapshot_cluster.get('source_inventory_cutoff'),
                    empty='No Tenant snapshot evidence',
                ),
                'capacity_available': capacity_available,
                'capacity_state': capacity['state'],
                'capacity_tone': _capacity_tone(str(capacity['state'])),
                'capacity_snapshot_state': str(capacity.get('snapshot_state') or 'Unknown').replace('_', ' ').title(),
                'capacity_reason': capacity['reason'],
                'committed_allocation': capacity['display']['committed'],
                'allocation_budget': capacity['display']['budget'],
                'allocation_headroom': capacity['display']['headroom'],
                'capacity_data_cutoff': present_user_datetime(
                    capacity.get('data_cutoff'),
                    empty='No committed capacity snapshot',
                ),
            }
        )

    return {
        'tenant_overview_clusters': cluster_rows,
        'tenant_collection_snapshot': _tenant_collection_snapshot(sync_state),
        'tenant_sync_state': sync_state,
        'tenant_attention_rows': _tenant_attention_rows(
            [
                finding
                for finding in get_active_recommendation_findings(domain='kubernetes')
                if str(finding.get('rule_key') or '').startswith('kubernetes.tenant.')
            ]
        ),
        'tenant_recent_activity_rows': _tenant_recent_activity(),
    }


def get_tenant_workspace_context(*, limit: int = 20) -> dict[str, Any]:
    """Return committed cross-child Tenant evidence for the integrated workspace.

    This context intentionally reads KAORI-owned committed state only. Provider
    mutations and live discovery stay in their owning services/adapters.
    """

    findings = [
        finding
        for finding in get_active_recommendation_findings(domain='kubernetes')
        if str(finding.get('rule_key') or '').startswith('kubernetes.tenant.')
    ]
    recent_credentials = _recent(TenantCredential, limit=limit)
    namespace_access_rows: list[dict[str, object]] = []
    for credential in recent_credentials:
        try:
            targets = credential_target_namespaces(credential)
            if not targets:
                namespace_access_rows.append(
                    {
                        'credential_public_id': credential.public_id,
                        'service_account_name': credential.service_account_name,
                        'credential_status': credential.status,
                        'error': 'No managed namespace is currently inside this credential scope.',
                    }
                )
                continue
            for namespace in targets:
                namespace_access_rows.append(build_namespace_access_package(credential, namespace).as_dict())
        except ValueError as exc:
            namespace_access_rows.append(
                {
                    'credential_public_id': credential.public_id,
                    'service_account_name': credential.service_account_name,
                    'credential_status': credential.status,
                    'error': str(exc),
                }
            )
    credential_grant_options = (
        TenantAccessGrant.query.filter_by(status='active', reconciliation_status='ready')
        .order_by(TenantAccessGrant.created_at.desc())
        .all()
    )
    deployer_namespace_options = (
        TenantNamespace.query.filter_by(provisioning_status='ready').order_by(TenantNamespace.created_at.desc()).all()
    )
    return {
        'credential_grant_options': credential_grant_options,
        'deployer_namespace_options': deployer_namespace_options,
        'recent_credentials': recent_credentials,
        'tenant_credential_count': TenantCredential.query.count(),
        'namespace_access_rows': namespace_access_rows[:limit],
        'managed_resources': _recent(TenantManagedResourceIntent, limit=limit),
        'domain_reservations': _recent(TenantDomainReservation, limit=limit),
        'exposure_policies': _recent(TenantExposurePolicy, limit=limit),
        'audit_evidence': _recent(TenantAuditEvidence, limit=limit),
        'advanced_intents': _recent(TenantAdvancedCapabilityIntent, limit=limit),
        'tenant_governance_findings': findings[:limit],
        'tenant_governance_finding_count': len(findings),
    }

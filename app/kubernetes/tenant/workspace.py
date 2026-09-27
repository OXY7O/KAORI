from __future__ import annotations

from typing import Any

from sqlalchemy import func

from app.common.job_execution_presentation import present_job_execution
from app.common.presentation import present_user_datetime
from app.intelligence.service import get_active_recommendation_findings
from app.kubernetes.inventory.overview import get_inventory_freshness_context
from app.kubernetes.tenant.capacity_governance import build_capacity_governance_summary
from app.kubernetes.tenant.credential import build_namespace_access_package, credential_target_namespaces
from app.models import Cluster
from app.models.job import JobExecution, JobPolicy
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
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.policies.presentation import present_interval
from app.platform_operations.jobs.registry import get_job_definition


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


def _cluster_tenant_counts() -> dict[str, int]:
    return {
        str(cluster_id): int(count)
        for cluster_id, count in (
            Tenant.query.with_entities(Tenant.cluster_id, func.count(Tenant.id))
            .group_by(Tenant.cluster_id)
            .all()
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


def _inventory_sync_context() -> dict[str, Any]:
    definition = get_job_definition('kubernetes.inventory.sync')
    policy = JobPolicy.query.filter_by(
        job_key=definition.key,
        scope_type=definition.scope_type,
        scope_key=definition.scope_key,
    ).first()
    jobs = JobExecution.query.filter(
        JobExecution.job_type == definition.job_type,
        JobExecution.operation == definition.operation,
    )
    active_job = (
        jobs.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        )
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    latest_job = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).first()

    automatic_enabled = policy.enabled if policy is not None else definition.default_enabled
    interval_minutes = policy.interval_minutes if policy is not None else definition.default_interval_minutes
    next_run_at = policy.next_run_at if policy is not None else None
    return {
        'automatic_enabled': automatic_enabled,
        'automatic_label': 'Enabled' if automatic_enabled else 'Manual Only',
        'interval_label': present_interval(interval_minutes),
        'next_run_label': present_user_datetime(
            next_run_at,
            empty='Pending scheduler plan' if automatic_enabled else 'Not Scheduled',
        ),
        'active_job': present_job_execution(active_job) if active_job is not None else None,
        'latest_job': present_job_execution(latest_job) if latest_job is not None else None,
    }


def get_tenant_overview_context() -> dict[str, Any]:
    """Compose Overview-only cross-cluster posture from committed KAORI evidence."""

    clusters = Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).all()
    tenant_counts = _cluster_tenant_counts()
    namespace_counts = _cluster_namespace_counts()
    total_tenants = sum(tenant_counts.values())

    cluster_rows: list[dict[str, Any]] = []
    for cluster in clusters:
        tenant_count = tenant_counts.get(str(cluster.id), 0)
        capacity = build_capacity_governance_summary(cluster.id)
        cluster_rows.append(
            {
                'id': str(cluster.id),
                'name': cluster.name,
                'environment': cluster.environment,
                'provider_status': cluster.status,
                'provider_tone': 'normal' if cluster.status == 'connected' else 'warning',
                'tenant_count': tenant_count,
                'namespace_count': namespace_counts.get(str(cluster.id), 0),
                'tenant_share_percent': round((tenant_count / total_tenants) * 100) if total_tenants else 0,
                'capacity_state': capacity['state'],
                'capacity_tone': _capacity_tone(str(capacity['state'])),
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

    freshness = get_inventory_freshness_context()
    sync = _inventory_sync_context()
    inventory_snapshot = {
        'status': freshness['status'],
        'tone': freshness['tone'],
        'description': freshness['description'],
        'last_sync_label': present_user_datetime(
            freshness['latest_collected_at'],
            empty='Never Collected',
        ),
        'oldest_sync_label': present_user_datetime(
            freshness['oldest_collected_at'],
            empty='No committed snapshot',
        ),
        'source_coverage_label': f"{freshness['committed_count']} / {freshness['cluster_count']}",
        'source_coverage_supporting': freshness['coverage_supporting'],
        'freshness_window_label': f"{freshness['freshness_window_hours']} Hours",
        'exception_label': freshness['exception_label'],
        'exceptions_supporting': freshness['exceptions_supporting'],
        **sync,
    }

    cluster_by_id = {str(cluster.id): cluster for cluster in clusters}
    recent_tenant_rows = []
    for tenant in Tenant.query.order_by(Tenant.updated_at.desc(), Tenant.id.asc()).limit(5).all():
        cluster = cluster_by_id.get(str(tenant.cluster_id))
        recent_tenant_rows.append(
            {
                'name': tenant.name,
                'lifecycle_status': tenant.lifecycle_status,
                'provider_key': tenant.provider_key,
                'provider_state': tenant.provider_state,
                'cluster_name': cluster.name if cluster is not None else 'Unknown cluster',
                'updated_at_label': present_user_datetime(tenant.updated_at, empty='Not recorded'),
            }
        )

    return {
        'tenant_overview_clusters': cluster_rows,
        'tenant_inventory_snapshot': inventory_snapshot,
        'tenant_recent_rows': recent_tenant_rows,
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

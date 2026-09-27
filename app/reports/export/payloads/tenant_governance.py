from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from app.intelligence.service import get_active_recommendation_findings
from app.models import (
    Cluster,
    Tenant,
    TenantAccessGrant,
    TenantAdvancedCapabilityIntent,
    TenantAuditEvidence,
    TenantCapacityDecision,
    TenantCredential,
    TenantDomainReservation,
    TenantEnvironment,
    TenantExposurePolicy,
    TenantManagedResourceIntent,
    TenantMembership,
    TenantNamespace,
)
from app.models.report import Report


def _iso(value: Any) -> str:
    if not isinstance(value, datetime):
        return ''
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat()


def _latest_timestamp(rows: Iterable[Any]) -> datetime | None:
    latest: datetime | None = None
    for row in rows:
        for name in ('event_at', 'last_reconciled_at', 'updated_at', 'created_at'):
            value = getattr(row, name, None)
            if not isinstance(value, datetime):
                continue
            normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
            if latest is None or normalized > latest:
                latest = normalized
    return latest


def _owner_label(credential: Any) -> str:
    owner = getattr(credential, 'owner_user', None)
    return str(
        getattr(owner, 'display_name', None)
        or getattr(owner, 'username', None)
        or getattr(credential, 'owner_user_id', '')
    )


def credential_row(credential: Any) -> dict[str, Any]:
    tenant = getattr(credential, 'tenant', None)
    return {
        'credential_id': str(getattr(credential, 'public_id', '') or ''),
        'tenant': str(getattr(tenant, 'name', None) or getattr(credential, 'tenant_id', '') or ''),
        'owner': _owner_label(credential),
        'credential_type': str(getattr(credential, 'credential_type', '') or ''),
        'purpose': str(getattr(credential, 'purpose', '') or ''),
        'application': str(getattr(credential, 'application_name', '') or ''),
        'delivery_method': str(getattr(credential, 'delivery_method', '') or ''),
        'status': str(getattr(credential, 'status', '') or ''),
        'reconciliation_status': str(getattr(credential, 'reconciliation_status', '') or ''),
        'service_account': str(getattr(credential, 'service_account_name', '') or ''),
        'jumpserver_reference': str(getattr(credential, 'jumpserver_reference', '') or ''),
        'renewal_due_at': _iso(getattr(credential, 'renewal_due_at', None)),
        'valid_until': _iso(getattr(credential, 'valid_until', None)),
        'rotation_generation': getattr(credential, 'rotation_generation', None),
        'last_reconciled_at': _iso(getattr(credential, 'last_reconciled_at', None)),
        'secret_material_persisted': False,
    }


def recommendation_row(finding: dict[str, Any]) -> dict[str, Any]:
    evidence = finding.get('evidence')
    evidence_map = evidence if isinstance(evidence, dict) else {}
    return {
        'rule_key': str(finding.get('rule_key') or ''),
        'title': str(finding.get('title') or 'Tenant Governance finding'),
        'description': str(
            finding.get('summary') or finding.get('condition_summary') or finding.get('description') or ''
        ),
        'severity': str(finding.get('severity') or 'info'),
        'priority': str(finding.get('priority') or ''),
        'status': str(finding.get('status') or 'available'),
        'tenant_id': str(evidence_map.get('tenant_id') or ''),
        'namespace': str(evidence_map.get('namespace') or evidence_map.get('kubernetes_namespace') or ''),
        'affected_scope': str(
            finding.get('affected_summary')
            or evidence_map.get('asset_key')
            or evidence_map.get('namespace')
            or evidence_map.get('cluster_id')
            or ''
        ),
        'recommended_action': str(finding.get('recommended_action') or ''),
        'tone': str(finding.get('severity') or 'info'),
    }


def _tenant_findings() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for finding in get_active_recommendation_findings(domain='kubernetes'):
        rule_key = str(finding.get('rule_key') or '')
        if rule_key.startswith('kubernetes.tenant.'):
            rows.append(recommendation_row(finding))
    return rows


def _tenant_scope(report: Report, cluster_id: str) -> tuple[list[Tenant], list[TenantNamespace]]:
    tenants = Tenant.query.filter_by(cluster_id=cluster_id).order_by(Tenant.name.asc()).all()
    namespace_query = TenantNamespace.query.filter_by(cluster_id=cluster_id)
    if report.namespace:
        namespace_query = namespace_query.filter(TenantNamespace.namespace == report.namespace)
    namespaces = namespace_query.order_by(TenantNamespace.namespace.asc()).all()
    if not report.namespace:
        return tenants, namespaces
    selected_tenant_ids = {row.environment.tenant_id for row in namespaces}
    return [row for row in tenants if row.id in selected_tenant_ids], namespaces


def _related_records(tenant_ids: list[str], cluster_id: str) -> dict[str, list[Any]]:
    if not tenant_ids:
        return {
            'environments': [],
            'memberships': [],
            'grants': [],
            'credentials': [],
            'managed_resources': [],
            'domain_reservations': [],
            'exposure_policies': [],
            'advanced_intents': [],
            'audit_evidence': [],
        }
    return {
        'environments': TenantEnvironment.query.filter(TenantEnvironment.tenant_id.in_(tenant_ids))
        .order_by(TenantEnvironment.tenant_id.asc(), TenantEnvironment.environment.asc())
        .all(),
        'memberships': TenantMembership.query.filter(TenantMembership.tenant_id.in_(tenant_ids))
        .order_by(TenantMembership.tenant_id.asc(), TenantMembership.subject_name.asc())
        .all(),
        'grants': TenantAccessGrant.query.filter(TenantAccessGrant.tenant_id.in_(tenant_ids))
        .order_by(TenantAccessGrant.tenant_id.asc(), TenantAccessGrant.id.asc())
        .all(),
        'credentials': TenantCredential.query.filter(TenantCredential.tenant_id.in_(tenant_ids))
        .order_by(TenantCredential.tenant_id.asc(), TenantCredential.id.asc())
        .all(),
        'managed_resources': TenantManagedResourceIntent.query.filter(
            TenantManagedResourceIntent.tenant_id.in_(tenant_ids)
        )
        .order_by(TenantManagedResourceIntent.tenant_id.asc(), TenantManagedResourceIntent.id.asc())
        .all(),
        'domain_reservations': TenantDomainReservation.query.filter(TenantDomainReservation.tenant_id.in_(tenant_ids))
        .order_by(TenantDomainReservation.tenant_id.asc(), TenantDomainReservation.id.asc())
        .all(),
        'exposure_policies': TenantExposurePolicy.query.filter(TenantExposurePolicy.tenant_id.in_(tenant_ids))
        .order_by(TenantExposurePolicy.tenant_id.asc(), TenantExposurePolicy.id.asc())
        .all(),
        'advanced_intents': TenantAdvancedCapabilityIntent.query.filter(
            TenantAdvancedCapabilityIntent.tenant_id.in_(tenant_ids)
        )
        .order_by(TenantAdvancedCapabilityIntent.tenant_id.asc(), TenantAdvancedCapabilityIntent.id.asc())
        .all(),
        'audit_evidence': TenantAuditEvidence.query.filter(
            TenantAuditEvidence.cluster_id == cluster_id,
            TenantAuditEvidence.tenant_id.in_(tenant_ids),
        )
        .order_by(TenantAuditEvidence.event_at.desc())
        .limit(250)
        .all(),
    }


def _namespace_scoped_records(
    report: Report,
    namespaces: list[TenantNamespace],
    records: dict[str, list[Any]],
) -> dict[str, list[Any]]:
    if not report.namespace:
        return records
    namespace_ids = {row.id for row in namespaces}
    grants = [
        row
        for row in records['grants']
        if row.scope_type != 'namespace' or row.tenant_namespace_id in namespace_ids
    ]
    return {
        **records,
        'grants': grants,
        'credentials': [
            row
            for row in records['credentials']
            if row.anchor_namespace_id is None
            or row.anchor_namespace_id in namespace_ids
            or (row.access_grant is not None and row.access_grant in grants)
        ],
        'managed_resources': [
            row for row in records['managed_resources'] if row.tenant_namespace_id in namespace_ids
        ],
        'exposure_policies': [
            row for row in records['exposure_policies'] if row.tenant_namespace_id in namespace_ids
        ],
        'audit_evidence': [
            row
            for row in records['audit_evidence']
            if row.tenant_namespace_id is None or row.tenant_namespace_id in namespace_ids
        ],
    }


def _capacity_decisions(report: Report, cluster_id: str) -> list[TenantCapacityDecision]:
    rows = (
        TenantCapacityDecision.query.filter(TenantCapacityDecision.cluster_id == cluster_id)
        .order_by(TenantCapacityDecision.created_at.desc())
        .limit(250)
        .all()
    )
    if report.namespace:
        rows = [row for row in rows if row.namespace == report.namespace]
    return rows


def _tenant_inventory(
    tenants: list[Tenant],
    environments: list[TenantEnvironment],
    namespaces: list[TenantNamespace],
) -> list[dict[str, Any]]:
    return [
        {
            'tenant': row.name,
            'tenant_id': row.id,
            'lifecycle_status': row.lifecycle_status,
            'ownership_status': row.ownership_status,
            'provider': row.provider_key,
            'provider_state': row.provider_state,
            'reconciliation_authority': row.reconciliation_authority,
            'environment_count': sum(1 for env in environments if env.tenant_id == row.id),
            'namespace_count': sum(1 for item in namespaces if item.environment.tenant_id == row.id),
            'updated_at': _iso(row.updated_at),
        }
        for row in tenants
    ]


def _namespace_inventory(namespaces: list[TenantNamespace]) -> list[dict[str, Any]]:
    return [
        {
            'tenant': row.environment.tenant.name,
            'environment': row.environment.environment,
            'namespace': row.namespace,
            'ownership_status': row.ownership_status,
            'provisioning_status': row.provisioning_status,
            'resource_profile': row.resource_profile.name if row.resource_profile is not None else 'Not Assigned',
            'resource_profile_class': (
                row.resource_profile.profile_class if row.resource_profile is not None else 'Not Assigned'
            ),
            'resource_profile_version': row.resource_profile_version,
            'allocation_customized': bool(row.allocation_customized),
            'reconciliation_message': row.provisioning_message or '',
            'last_reconciled_at': _iso(row.last_reconciled_at),
        }
        for row in namespaces
    ]


def _allocation_posture(
    namespaces: list[TenantNamespace],
    decisions: list[TenantCapacityDecision],
    environment_by_id: dict[int, TenantEnvironment],
) -> list[dict[str, Any]]:
    rows = [
        {
            'tenant': row.environment.tenant.name,
            'environment': row.environment.environment,
            'namespace': row.namespace,
            'resource_profile': row.resource_profile.name if row.resource_profile is not None else 'Not Assigned',
            'resource_profile_version': row.resource_profile_version,
            'allocation_customized': bool(row.allocation_customized),
            'effective_quota': row.allocation_quota_json or {},
            'effective_limit_defaults': row.allocation_limit_defaults_json or {},
            'capacity_decision_id': row.capacity_decision_id,
            'provisioning_status': row.provisioning_status,
        }
        for row in namespaces
    ]
    rows.extend(_capacity_decision_row(row, environment_by_id) for row in decisions)
    return rows


def _capacity_decision_row(
    row: TenantCapacityDecision,
    environment_by_id: dict[int, TenantEnvironment],
) -> dict[str, Any]:
    environment = environment_by_id.get(row.tenant_environment_id)
    return {
        'tenant': environment.tenant.name if environment is not None else 'Not Available',
        'environment': environment.environment if environment is not None else 'Not Available',
        'namespace': row.namespace,
        'operation': row.operation,
        'decision': row.decision,
        'capacity_state': row.capacity_state,
        'resource_profile_version': row.resource_profile_version,
        'data_cutoff': _iso(row.data_cutoff),
        'created_at': _iso(row.created_at),
    }


def _access_posture(
    memberships: list[TenantMembership],
    grants: list[TenantAccessGrant],
    tenant_by_id: dict[str, Tenant],
) -> list[dict[str, Any]]:
    rows = [
        {
            'record_type': 'membership',
            'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
            'principal_type': row.principal_type,
            'subject': row.subject_name,
            'membership_status': row.status,
            'access_profile': '',
            'scope': '',
            'target': '',
            'reconciliation_status': '',
        }
        for row in memberships
    ]
    rows.extend(_grant_row(row, tenant_by_id) for row in grants)
    return rows


def _grant_row(row: TenantAccessGrant, tenant_by_id: dict[str, Tenant]) -> dict[str, Any]:
    target = 'Tenant'
    if row.namespace is not None:
        target = row.namespace.namespace
    elif row.environment is not None:
        target = row.environment.environment
    return {
        'record_type': 'access_grant',
        'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
        'principal_type': row.membership.principal_type,
        'subject': row.membership.subject_name,
        'membership_status': row.membership.status,
        'access_profile': f'{row.access_profile} v{row.access_profile_version}',
        'scope': row.scope_type,
        'target': target,
        'grant_status': row.status,
        'reconciliation_status': row.reconciliation_status,
        'last_reconciled_at': _iso(row.last_reconciled_at),
    }


def _managed_resource_posture(
    managed_resources: list[TenantManagedResourceIntent],
    domain_reservations: list[TenantDomainReservation],
    exposure_policies: list[TenantExposurePolicy],
    advanced_intents: list[TenantAdvancedCapabilityIntent],
    tenant_by_id: dict[str, Tenant],
    namespace_by_id: dict[int, TenantNamespace],
) -> list[dict[str, Any]]:
    rows = [_managed_resource_row(row, tenant_by_id, namespace_by_id) for row in managed_resources]
    rows.extend(_domain_reservation_row(row, tenant_by_id) for row in domain_reservations)
    rows.extend(_exposure_policy_row(row, tenant_by_id) for row in exposure_policies)
    rows.extend(_advanced_intent_row(row, tenant_by_id) for row in advanced_intents)
    return rows


def _managed_resource_row(
    row: TenantManagedResourceIntent,
    tenant_by_id: dict[str, Tenant],
    namespace_by_id: dict[int, TenantNamespace],
) -> dict[str, Any]:
    namespace = namespace_by_id.get(row.tenant_namespace_id)
    return {
        'record_type': 'managed_resource',
        'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
        'namespace': namespace.namespace if namespace is not None else 'Not Available',
        'kind': row.resource_kind,
        'mode': row.mode,
        'resource': row.resource_name,
        'status': row.status,
        'generation': row.rotation_generation,
        'last_reconciled_at': _iso(row.last_reconciled_at),
    }


def _domain_reservation_row(row: TenantDomainReservation, tenant_by_id: dict[str, Tenant]) -> dict[str, Any]:
    return {
        'record_type': 'domain_reservation',
        'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
        'environment': row.environment.environment,
        'kind': 'domain',
        'mode': row.match_mode,
        'resource': row.hostname_pattern,
        'status': row.status,
    }


def _exposure_policy_row(row: TenantExposurePolicy, tenant_by_id: dict[str, Tenant]) -> dict[str, Any]:
    return {
        'record_type': 'exposure_policy',
        'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
        'namespace': row.namespace.namespace,
        'kind': 'service_exposure',
        'mode': row.profile_key,
        'resource': row.namespace.namespace,
        'status': row.status,
    }


def _advanced_intent_row(
    row: TenantAdvancedCapabilityIntent,
    tenant_by_id: dict[str, Tenant],
) -> dict[str, Any]:
    return {
        'record_type': 'advanced_capability',
        'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
        'namespace': row.namespace.namespace if row.namespace is not None else '',
        'kind': row.resource_kind,
        'mode': row.capability_key,
        'resource': row.resource_name,
        'status': row.status,
        'generation': row.generation,
        'last_reconciled_at': _iso(row.last_reconciled_at),
    }


def _provider_posture(tenants: list[Tenant]) -> list[dict[str, Any]]:
    return [_provider_row(row) for row in tenants]


def _provider_row(row: Tenant) -> dict[str, Any]:
    provider_evidence = row.provider_evidence_json if isinstance(row.provider_evidence_json, dict) else {}
    capsule = provider_evidence.get('capsule')
    capsule_map = capsule if isinstance(capsule, dict) else {}
    capabilities = capsule_map.get('capabilities')
    return {
        'tenant': row.name,
        'provider': row.provider_key,
        'provider_state': row.provider_state,
        'reconciliation_authority': row.reconciliation_authority,
        'capsule_installed': capsule_map.get('installed', 'Not Available'),
        'capsule_version': capsule_map.get('reported_version') or 'Not Available',
        'capsule_api_versions': capsule_map.get('tenant_api_versions') or [],
        'capabilities': capabilities if isinstance(capabilities, dict) else {},
        'evidence_updated_at': _iso(row.updated_at),
    }


def _activity_evidence(
    audit_evidence: list[TenantAuditEvidence],
    tenant_by_id: dict[str, Tenant],
) -> list[dict[str, Any]]:
    return [
        {
            'event_at': _iso(row.event_at),
            'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else 'Unmanaged',
            'namespace': row.kubernetes_namespace or '',
            'identity_class': row.identity_class,
            'principal_kind': row.principal_kind,
            'verb': row.verb,
            'resource': row.resource or '',
            'resource_name': row.resource_name or '',
            'outcome': row.outcome,
            'response_code': row.response_code,
            'correlation_status': row.correlation_status,
            'credential_type': row.credential_type or '',
            'credential_status': row.credential_status or '',
        }
        for row in audit_evidence
    ]


def _summary(
    tenants: list[Tenant],
    namespaces: list[TenantNamespace],
    grants: list[TenantAccessGrant],
    credentials: list[TenantCredential],
    managed_resources: list[TenantManagedResourceIntent],
    advanced_intents: list[TenantAdvancedCapabilityIntent],
    findings: list[dict[str, Any]],
) -> dict[str, int]:
    credential_attention = sum(
        1 for row in credentials if row.status in {'renewal_due', 'suspended', 'expired', 'revoked'}
    )
    drifted = sum(1 for row in namespaces if row.provisioning_status in {'drifted', 'failed'})
    drifted += sum(1 for row in grants if row.reconciliation_status in {'drifted', 'failed'})
    drifted += sum(1 for row in managed_resources if row.status in {'drifted', 'failed'})
    drifted += sum(1 for row in advanced_intents if row.status in {'drifted', 'failed'})
    return {
        'tenants': len(tenants),
        'namespaces': len(namespaces),
        'active_grants': sum(1 for row in grants if row.status == 'active'),
        'credential_attention': credential_attention,
        'governance_findings': len(findings),
        'drift_or_failure': drifted,
    }


def _source_evidence(latest: datetime, audit_evidence: list[TenantAuditEvidence]) -> list[dict[str, str]]:
    return [
        {'source': 'KAORI Tenant Management', 'freshness': 'Committed', 'last_collected': _iso(latest)},
        {
            'source': 'KAORI Intelligence',
            'freshness': 'Evaluated from committed Tenant evidence',
            'last_collected': _iso(latest),
        },
        {
            'source': 'Kubernetes Audit Correlation',
            'freshness': 'Committed' if audit_evidence else 'Not Available',
            'last_collected': _iso(audit_evidence[0].event_at) if audit_evidence else '',
        },
    ]


def get_report_tenant_governance_payload(report: Report) -> dict[str, Any]:
    cluster_id = str(report.cluster_id or '').strip()
    cluster = Cluster.query.filter_by(id=cluster_id).first()
    if cluster is None:
        return {'_error': 'Selected Kubernetes cluster is no longer available.'}

    tenants, namespaces = _tenant_scope(report, cluster_id)
    tenant_ids = [row.id for row in tenants]
    records = _namespace_scoped_records(report, namespaces, _related_records(tenant_ids, cluster_id))
    decisions = _capacity_decisions(report, cluster_id)
    environments = records['environments']
    tenant_by_id = {row.id: row for row in tenants}
    environment_by_id = {row.id: row for row in environments}
    namespace_by_id = {row.id: row for row in namespaces}
    findings = _tenant_findings()

    all_rows = [
        *tenants,
        *environments,
        *namespaces,
        *records['memberships'],
        *records['grants'],
        *records['credentials'],
        *records['managed_resources'],
        *records['domain_reservations'],
        *records['exposure_policies'],
        *records['advanced_intents'],
        *decisions,
        *records['audit_evidence'],
    ]
    latest = _latest_timestamp(all_rows) or datetime.now(UTC)
    provider_posture = _provider_posture(tenants)
    evidence_boundary = {
        'source': 'Committed KAORI Tenant Management state',
        'provider_query_at_render': 'Disabled',
        'data_cutoff': _iso(latest),
        'tenant_records': len(tenants),
        'capacity_evidence': 'Available' if decisions else 'Not Available',
        'audit_evidence': 'Available' if records['audit_evidence'] else 'Not Available',
        'intelligence_evidence': 'Available' if findings else 'No Active Findings',
        'provider_evidence': 'Available' if provider_posture else 'Not Available',
        'secret_material_persisted': False,
    }
    recommendations = [
        {
            'title': row['title'],
            'description': row['recommended_action'] or row['description'],
            'priority': row['priority'],
            'severity': row['severity'],
            'affected_scope': row['affected_scope'],
            'source_rule': row['rule_key'],
            'tone': row['tone'],
        }
        for row in findings
    ]

    return {
        'cluster': {'id': cluster.id, 'name': cluster.name, 'environment': cluster.environment},
        'data_cutoff': _iso(latest),
        'summary': _summary(
            tenants,
            namespaces,
            records['grants'],
            records['credentials'],
            records['managed_resources'],
            records['advanced_intents'],
            findings,
        ),
        'integration_status': {
            'label': 'Committed Evidence',
            'status': 'ready',
            'description': 'Tenant report renderers use committed KAORI state and do not query providers.',
        },
        'tenant_inventory': _tenant_inventory(tenants, environments, namespaces),
        'namespace_inventory': _namespace_inventory(namespaces),
        'allocation_posture': _allocation_posture(namespaces, decisions, environment_by_id),
        'access_posture': _access_posture(records['memberships'], records['grants'], tenant_by_id),
        'credential_posture': [credential_row(row) for row in records['credentials']],
        'managed_resource_posture': _managed_resource_posture(
            records['managed_resources'],
            records['domain_reservations'],
            records['exposure_policies'],
            records['advanced_intents'],
            tenant_by_id,
            namespace_by_id,
        ),
        'provider_posture': provider_posture,
        'governance_findings': findings,
        'activity_evidence': _activity_evidence(records['audit_evidence'], tenant_by_id),
        'actionable_recommendations': recommendations,
        'evidence_boundary': evidence_boundary,
        'source_evidence': _source_evidence(latest, records['audit_evidence']),
    }

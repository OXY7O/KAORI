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


def _owner_label(credential: TenantCredential) -> str:
    owner = credential.owner_user
    return str(
        getattr(owner, 'display_name', None)
        or getattr(owner, 'username', None)
        or credential.owner_user_id
    )


def _tenant_findings() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for finding in get_active_recommendation_findings(domain='kubernetes'):
        rule_key = str(finding.get('rule_key') or '')
        if not rule_key.startswith('kubernetes.tenant.'):
            continue
        evidence = finding.get('evidence')
        evidence_map = evidence if isinstance(evidence, dict) else {}
        rows.append(
            {
                'rule_key': rule_key,
                'title': str(finding.get('title') or 'Tenant Governance finding'),
                'description': str(
                    finding.get('summary')
                    or finding.get('condition_summary')
                    or finding.get('description')
                    or ''
                ),
                'severity': str(finding.get('severity') or 'info'),
                'priority': str(finding.get('priority') or ''),
                'status': str(finding.get('status') or 'available'),
                'affected_scope': str(
                    finding.get('affected_summary')
                    or evidence_map.get('asset_key')
                    or evidence_map.get('cluster_id')
                    or ''
                ),
                'recommended_action': str(finding.get('recommended_action') or ''),
                'tone': str(finding.get('severity') or 'info'),
            }
        )
    return rows


def get_report_tenant_governance_payload(report: Report) -> dict[str, Any]:
    cluster_id = str(report.cluster_id or '').strip()
    cluster = Cluster.query.filter_by(id=cluster_id).first()
    if cluster is None:
        return {'_error': 'Selected Kubernetes cluster is no longer available.'}

    tenant_rows = Tenant.query.filter_by(cluster_id=cluster_id).order_by(Tenant.name.asc()).all()
    tenant_ids = [row.id for row in tenant_rows]

    namespace_query = TenantNamespace.query.filter_by(cluster_id=cluster_id)
    if report.namespace:
        namespace_query = namespace_query.filter(TenantNamespace.namespace == report.namespace)
    namespaces = namespace_query.order_by(TenantNamespace.namespace.asc()).all()
    if report.namespace:
        selected_tenant_ids = {row.environment.tenant_id for row in namespaces}
        tenant_rows = [row for row in tenant_rows if row.id in selected_tenant_ids]
        tenant_ids = [row.id for row in tenant_rows]

    if tenant_ids:
        environments = (
            TenantEnvironment.query.filter(TenantEnvironment.tenant_id.in_(tenant_ids))
            .order_by(TenantEnvironment.tenant_id.asc(), TenantEnvironment.environment.asc())
            .all()
        )
        memberships = (
            TenantMembership.query.filter(TenantMembership.tenant_id.in_(tenant_ids))
            .order_by(TenantMembership.tenant_id.asc(), TenantMembership.subject_name.asc())
            .all()
        )
        grants = (
            TenantAccessGrant.query.filter(TenantAccessGrant.tenant_id.in_(tenant_ids))
            .order_by(TenantAccessGrant.tenant_id.asc(), TenantAccessGrant.id.asc())
            .all()
        )
        credentials = (
            TenantCredential.query.filter(TenantCredential.tenant_id.in_(tenant_ids))
            .order_by(TenantCredential.tenant_id.asc(), TenantCredential.id.asc())
            .all()
        )
        managed_resources = (
            TenantManagedResourceIntent.query.filter(TenantManagedResourceIntent.tenant_id.in_(tenant_ids))
            .order_by(TenantManagedResourceIntent.tenant_id.asc(), TenantManagedResourceIntent.id.asc())
            .all()
        )
        domain_reservations = (
            TenantDomainReservation.query.filter(TenantDomainReservation.tenant_id.in_(tenant_ids))
            .order_by(TenantDomainReservation.tenant_id.asc(), TenantDomainReservation.id.asc())
            .all()
        )
        exposure_policies = (
            TenantExposurePolicy.query.filter(TenantExposurePolicy.tenant_id.in_(tenant_ids))
            .order_by(TenantExposurePolicy.tenant_id.asc(), TenantExposurePolicy.id.asc())
            .all()
        )
        advanced_intents = (
            TenantAdvancedCapabilityIntent.query.filter(TenantAdvancedCapabilityIntent.tenant_id.in_(tenant_ids))
            .order_by(TenantAdvancedCapabilityIntent.tenant_id.asc(), TenantAdvancedCapabilityIntent.id.asc())
            .all()
        )
        audit_evidence = (
            TenantAuditEvidence.query.filter(
                TenantAuditEvidence.cluster_id == cluster_id,
                TenantAuditEvidence.tenant_id.in_(tenant_ids),
            )
            .order_by(TenantAuditEvidence.event_at.desc())
            .limit(250)
            .all()
        )
    else:
        environments = []
        memberships = []
        grants = []
        credentials = []
        managed_resources = []
        domain_reservations = []
        exposure_policies = []
        advanced_intents = []
        audit_evidence = []

    namespace_ids = {row.id for row in namespaces}
    if report.namespace:
        grants = [
            row
            for row in grants
            if row.scope_type != 'namespace' or row.tenant_namespace_id in namespace_ids
        ]
        credentials = [
            row
            for row in credentials
            if row.anchor_namespace_id in {None, *namespace_ids}
            or (row.access_grant is not None and row.access_grant in grants)
        ]
        managed_resources = [row for row in managed_resources if row.tenant_namespace_id in namespace_ids]
        exposure_policies = [row for row in exposure_policies if row.tenant_namespace_id in namespace_ids]
        audit_evidence = [row for row in audit_evidence if row.tenant_namespace_id in {None, *namespace_ids}]

    decisions = (
        TenantCapacityDecision.query.filter(TenantCapacityDecision.cluster_id == cluster_id)
        .order_by(TenantCapacityDecision.created_at.desc())
        .limit(250)
        .all()
    )
    if report.namespace:
        decisions = [row for row in decisions if row.namespace == report.namespace]

    tenant_by_id = {row.id: row for row in tenant_rows}
    environment_by_id = {row.id: row for row in environments}
    namespace_by_id = {row.id: row for row in namespaces}

    tenant_inventory = [
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
        for row in tenant_rows
    ]

    namespace_inventory = [
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

    allocation_posture = [
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
    allocation_posture.extend(
        {
            'tenant': (
                environment_by_id[row.tenant_environment_id].tenant.name
                if row.tenant_environment_id in environment_by_id
                else 'Not Available'
            ),
            'environment': (
                environment_by_id[row.tenant_environment_id].environment
                if row.tenant_environment_id in environment_by_id
                else 'Not Available'
            ),
            'namespace': row.namespace,
            'operation': row.operation,
            'decision': row.decision,
            'capacity_state': row.capacity_state,
            'resource_profile_version': row.resource_profile_version,
            'data_cutoff': _iso(row.data_cutoff),
            'created_at': _iso(row.created_at),
        }
        for row in decisions
    )

    access_posture = [
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
    access_posture.extend(
        {
            'record_type': 'access_grant',
            'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
            'principal_type': row.membership.principal_type,
            'subject': row.membership.subject_name,
            'membership_status': row.membership.status,
            'access_profile': f'{row.access_profile} v{row.access_profile_version}',
            'scope': row.scope_type,
            'target': (
                row.namespace.namespace
                if row.namespace is not None
                else (row.environment.environment if row.environment is not None else 'Tenant')
            ),
            'grant_status': row.status,
            'reconciliation_status': row.reconciliation_status,
            'last_reconciled_at': _iso(row.last_reconciled_at),
        }
        for row in grants
    )

    credential_posture = [
        {
            'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
            'owner': _owner_label(row),
            'credential_type': row.credential_type,
            'purpose': row.purpose,
            'application': row.application_name or '',
            'delivery_method': row.delivery_method,
            'status': row.status,
            'reconciliation_status': row.reconciliation_status,
            'service_account': row.service_account_name,
            'jumpserver_reference': row.jumpserver_reference or '',
            'renewal_due_at': _iso(row.renewal_due_at),
            'valid_until': _iso(row.valid_until),
            'rotation_generation': row.rotation_generation,
            'secret_material_persisted': False,
        }
        for row in credentials
    ]

    managed_resource_posture = [
        {
            'record_type': 'managed_resource',
            'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
            'namespace': namespace_by_id[row.tenant_namespace_id].namespace
            if row.tenant_namespace_id in namespace_by_id
            else 'Not Available',
            'kind': row.resource_kind,
            'mode': row.mode,
            'resource': row.resource_name,
            'status': row.status,
            'generation': row.rotation_generation,
            'last_reconciled_at': _iso(row.last_reconciled_at),
        }
        for row in managed_resources
    ]
    managed_resource_posture.extend(
        {
            'record_type': 'domain_reservation',
            'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
            'environment': row.environment.environment,
            'kind': 'domain',
            'mode': row.match_mode,
            'resource': row.hostname_pattern,
            'status': row.status,
        }
        for row in domain_reservations
    )
    managed_resource_posture.extend(
        {
            'record_type': 'exposure_policy',
            'tenant': tenant_by_id[row.tenant_id].name if row.tenant_id in tenant_by_id else row.tenant_id,
            'namespace': row.namespace.namespace,
            'kind': 'service_exposure',
            'mode': row.profile_key,
            'resource': row.namespace.namespace,
            'status': row.status,
        }
        for row in exposure_policies
    )
    managed_resource_posture.extend(
        {
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
        for row in advanced_intents
    )

    provider_posture = []
    for row in tenant_rows:
        provider_evidence = row.provider_evidence_json if isinstance(row.provider_evidence_json, dict) else {}
        capsule = provider_evidence.get('capsule')
        capsule_map = capsule if isinstance(capsule, dict) else {}
        capabilities = capsule_map.get('capabilities')
        provider_posture.append(
            {
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
        )

    governance_findings = _tenant_findings()
    actionable_recommendations = [
        {
            'title': row['title'],
            'description': row['recommended_action'] or row['description'],
            'priority': row['priority'],
            'severity': row['severity'],
            'affected_scope': row['affected_scope'],
            'source_rule': row['rule_key'],
            'tone': row['tone'],
        }
        for row in governance_findings
    ]

    activity_evidence = [
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

    all_rows: list[Any] = [
        *tenant_rows,
        *environments,
        *namespaces,
        *memberships,
        *grants,
        *credentials,
        *managed_resources,
        *domain_reservations,
        *exposure_policies,
        *advanced_intents,
        *decisions,
        *audit_evidence,
    ]
    latest = _latest_timestamp(all_rows) or datetime.now(UTC)
    credential_attention = sum(
        1 for row in credentials if row.status in {'renewal_due', 'suspended', 'expired', 'revoked'}
    )
    drifted = sum(1 for row in namespaces if row.provisioning_status in {'drifted', 'failed'})
    drifted += sum(1 for row in grants if row.reconciliation_status in {'drifted', 'failed'})
    drifted += sum(1 for row in managed_resources if row.status in {'drifted', 'failed'})
    drifted += sum(1 for row in advanced_intents if row.status in {'drifted', 'failed'})

    evidence_boundary = {
        'source': 'Committed KAORI Tenant Management state',
        'provider_query_at_render': 'Disabled',
        'data_cutoff': _iso(latest),
        'tenant_records': len(tenant_rows),
        'capacity_evidence': 'Available' if decisions else 'Not Available',
        'audit_evidence': 'Available' if audit_evidence else 'Not Available',
        'intelligence_evidence': 'Available' if governance_findings else 'No Active Findings',
        'provider_evidence': 'Available' if provider_posture else 'Not Available',
        'secret_material_persisted': False,
    }

    return {
        'cluster': {'id': cluster.id, 'name': cluster.name, 'environment': cluster.environment},
        'data_cutoff': _iso(latest),
        'summary': {
            'tenants': len(tenant_rows),
            'namespaces': len(namespaces),
            'active_grants': sum(1 for row in grants if row.status == 'active'),
            'credential_attention': credential_attention,
            'governance_findings': len(governance_findings),
            'drift_or_failure': drifted,
        },
        'integration_status': {
            'label': 'Committed Evidence',
            'status': 'ready',
            'description': 'Tenant report renderers use committed KAORI state and do not query providers.',
        },
        'tenant_inventory': tenant_inventory,
        'namespace_inventory': namespace_inventory,
        'allocation_posture': allocation_posture,
        'access_posture': access_posture,
        'credential_posture': credential_posture,
        'managed_resource_posture': managed_resource_posture,
        'provider_posture': provider_posture,
        'governance_findings': governance_findings,
        'activity_evidence': activity_evidence,
        'actionable_recommendations': actionable_recommendations,
        'evidence_boundary': evidence_boundary,
        'source_evidence': [
            {
                'source': 'KAORI Tenant Management',
                'freshness': 'Committed',
                'last_collected': _iso(latest),
            },
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
        ],
    }

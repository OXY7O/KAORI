from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.common import (
    column,
    integer,
    mapping,
    metric_value,
    sequence,
    table,
)
from app.reports.export.xlsx.analytics_schema import (
    AnalyticsExportContext,
    AnalyticsTableData,
    AnalyticsWorkbookData,
    AnalyticsWorkbookProfile,
)


def _table_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    return sequence(payload.get(key))


def prepare_tenant_governance(
    payload: Mapping[str, Any],
    context: AnalyticsExportContext,
    profile: AnalyticsWorkbookProfile,
) -> AnalyticsWorkbookData:
    summary = mapping(payload.get('summary'))
    metrics = tuple(
        metric_value(spec, value)
        for spec, value in zip(
            profile.metric_specs,
            (
                integer(summary.get('tenants')),
                integer(summary.get('namespaces')),
                integer(summary.get('active_grants')),
                integer(summary.get('credential_attention')),
            ),
            strict=True,
        )
    )

    tenant_rows = _table_rows(payload, 'tenant_inventory')
    namespace_rows = _table_rows(payload, 'namespace_inventory')
    access_rows = _table_rows(payload, 'access_posture')
    credential_rows = _table_rows(payload, 'credential_posture')
    allocation_rows = _table_rows(payload, 'allocation_posture')

    governance_rows: list[dict[str, Any]] = []
    for row in _table_rows(payload, 'managed_resource_posture'):
        governance_rows.append(
            {
                'record_type': row.get('record_type'),
                'tenant': row.get('tenant'),
                'scope': row.get('namespace') or row.get('environment') or '',
                'resource': row.get('resource'),
                'status': row.get('status'),
                'severity': '',
                'detail': row.get('mode') or row.get('kind') or '',
                'recommendation': '',
            }
        )
    for row in _table_rows(payload, 'provider_posture'):
        governance_rows.append(
            {
                'record_type': 'provider',
                'tenant': row.get('tenant'),
                'scope': row.get('provider'),
                'resource': row.get('reconciliation_authority'),
                'status': row.get('provider_state'),
                'severity': '',
                'detail': row.get('capsule_version'),
                'recommendation': '',
            }
        )
    for row in _table_rows(payload, 'governance_findings'):
        governance_rows.append(
            {
                'record_type': 'finding',
                'tenant': row.get('affected_scope') or '',
                'scope': row.get('rule_key'),
                'resource': row.get('title'),
                'status': row.get('status'),
                'severity': row.get('severity'),
                'detail': row.get('description'),
                'recommendation': row.get('recommended_action'),
            }
        )
    for row in _table_rows(payload, 'activity_evidence')[:100]:
        governance_rows.append(
            {
                'record_type': 'audit',
                'tenant': row.get('tenant'),
                'scope': row.get('namespace'),
                'resource': f'{row.get("verb", "")} {row.get("resource", "")}'.strip(),
                'status': row.get('correlation_status'),
                'severity': row.get('outcome'),
                'detail': row.get('resource_name') or '',
                'recommendation': '',
            }
        )

    tables: list[AnalyticsTableData] = [
        table(
            'Tenants',
            'Tenant Governance Inventory',
            'Canonical Tenant lifecycle, provider authority, ownership, and environment coverage.',
            (
                column('tenant', 'Tenant', 'Canonical Tenant name.', width=34),
                column('lifecycle_status', 'Lifecycle', 'Committed Tenant lifecycle status.', width=16),
                column('ownership_status', 'Ownership', 'Managed/discovered/adopted ownership state.', width=16),
                column('provider', 'Provider', 'Configured provider key.', width=22),
                column('provider_state', 'Provider State', 'Committed provider state.', width=20),
                column('reconciliation_authority', 'Authority', 'Current reconciliation authority.', width=22),
                column(
                    'environment_count',
                    'Environments',
                    'Tenant environment count.',
                    data_type='integer',
                    number_format='#,##0',
                    width=14,
                ),
                column(
                    'namespace_count',
                    'Namespaces',
                    'Managed/adopted namespace count.',
                    data_type='integer',
                    number_format='#,##0',
                    width=14,
                ),
                column('updated_at', 'Updated At', 'Committed Tenant update timestamp.', width=24),
            ),
            tenant_rows,
        ),
        table(
            'Namespaces',
            'Tenant Environment & Namespace Inventory',
            'Committed namespace identity, Resource Profile lineage, ownership, and reconciliation state.',
            (
                column('tenant', 'Tenant', 'Tenant owner.', width=30),
                column('environment', 'Environment', 'Tenant environment.', width=16),
                column('namespace', 'Namespace', 'Kubernetes namespace.', width=34),
                column('ownership_status', 'Ownership', 'Namespace ownership state.', width=16),
                column(
                    'provisioning_status', 'Provisioning', 'Committed provisioning/reconciliation status.', width=18
                ),
                column('resource_profile', 'Resource Profile', 'Effective Resource Profile name.', width=24),
                column('resource_profile_class', 'Profile Class', 'Built-in or Custom profile class.', width=16),
                column(
                    'resource_profile_version',
                    'Profile Version',
                    'Frozen profile version.',
                    data_type='integer',
                    number_format='#,##0',
                    width=14,
                ),
                column('allocation_customized', 'Customized', 'Whether allocation uses Custom semantics.', width=14),
                column(
                    'last_reconciled_at',
                    'Last Reconciled',
                    'Last committed namespace reconciliation timestamp.',
                    width=24,
                ),
            ),
            namespace_rows,
        ),
        table(
            'Access',
            'Tenant Memberships & Access Grants',
            'Principal registration, Access Profile, explicit scope, lifecycle, and RBAC reconciliation evidence.',
            (
                column('record_type', 'Record Type', 'Membership or Access Grant.', width=16),
                column('tenant', 'Tenant', 'Tenant scope.', width=28),
                column('principal_type', 'Principal Type', 'User, group, or service account.', width=18),
                column('subject', 'Subject', 'Kubernetes authentication subject.', width=34),
                column('membership_status', 'Membership', 'Tenant Membership lifecycle status.', width=16),
                column('access_profile', 'Access Profile', 'Versioned Access Profile.', width=20),
                column('scope', 'Scope', 'Tenant, Environment, or Namespace scope.', width=16),
                column('target', 'Target', 'Scoped target.', width=30),
                column('grant_status', 'Grant Status', 'Access Grant lifecycle state.', width=16),
                column('reconciliation_status', 'Reconciliation', 'Effective Kubernetes RBAC posture.', width=18),
                column('last_reconciled_at', 'Last Reconciled', 'Last RBAC reconciliation timestamp.', width=24),
            ),
            access_rows,
        ),
        table(
            'Credentials',
            'Tenant Credential Lifecycle',
            'Non-secret ownership, delivery, review, rotation, and reconciliation metadata.',
            (
                column('tenant', 'Tenant', 'Tenant scope.', width=28),
                column('owner', 'Owner', 'Individual credential owner.', width=28),
                column('credential_type', 'Credential Type', 'Human, admin, or deployer credential class.', width=24),
                column('delivery_method', 'Delivery', 'Approved delivery method.', width=24),
                column('purpose', 'Purpose', 'Credential purpose.', width=30),
                column('application', 'Application', 'CI/CD application identity when applicable.', width=24),
                column('status', 'Status', 'Credential entitlement lifecycle.', width=16),
                column('reconciliation_status', 'Reconciliation', 'Effective credential resource state.', width=18),
                column('service_account', 'ServiceAccount', 'Non-secret Kubernetes principal name.', width=30),
                column('renewal_due_at', 'Renewal Due', 'Review/renewal due timestamp.', width=24),
                column('valid_until', 'Valid Until', 'Entitlement validity boundary.', width=24),
                column(
                    'rotation_generation',
                    'Generation',
                    'Credential rotation generation.',
                    data_type='integer',
                    number_format='#,##0',
                    width=12,
                ),
            ),
            credential_rows,
        ),
        table(
            'Allocations',
            'Tenant Allocation & Capacity Evidence',
            'Effective Resource Profile allocation and capacity-admission evidence; missing values remain explicit.',
            (
                column('tenant', 'Tenant', 'Tenant owner.', width=28),
                column('environment', 'Environment', 'Tenant environment.', width=16),
                column('namespace', 'Namespace', 'Managed namespace.', width=32),
                column('resource_profile', 'Resource Profile', 'Effective profile name.', width=24),
                column('resource_profile_version', 'Profile Version', 'Frozen profile version.', data_type='integer', number_format='#,##0', width=14),
                column('allocation_customized', 'Customized', 'Whether Custom profile semantics apply.', width=14),
                column('effective_quota', 'Effective Quota', 'Committed ResourceQuota allocation.', width=46),
                column('effective_limit_defaults', 'Effective Limits', 'Committed LimitRange defaults.', width=46),
                column('operation', 'Decision Operation', 'Create/increase/decrease/no-change decision.', width=18),
                column('decision', 'Decision', 'Capacity admission allow/block.', width=14),
                column('capacity_state', 'Capacity State', 'Committed capacity posture.', width=20),
                column('data_cutoff', 'Data Cut-off', 'Capacity evidence cut-off.', width=24),
            ),
            allocation_rows,
        ),
        table(
            'Governance',
            'Tenant Governance Evidence',
            'Managed-resource, provider, Intelligence finding, and correlated audit evidence in one review sheet.',
            (
                column(
                    'record_type', 'Record Type', 'Managed resource, provider, finding, or audit evidence.', width=18
                ),
                column('tenant', 'Tenant / Affected Scope', 'Tenant identity or finding scope.', width=30),
                column('scope', 'Scope / Source', 'Namespace, provider, or rule source.', width=34),
                column('resource', 'Resource / Finding', 'Managed resource or governance finding.', width=42),
                column('status', 'Status', 'Committed status.', width=18),
                column('severity', 'Severity / Outcome', 'Finding severity or audit outcome.', width=18),
                column('detail', 'Evidence Detail', 'Non-secret supporting evidence.', width=54),
                column(
                    'recommendation',
                    'Recommendation',
                    'Canonical Intelligence recommendation when available.',
                    width=54,
                ),
            ),
            governance_rows,
        ),
    ]

    findings = integer(summary.get('governance_findings'))
    drift = integer(summary.get('drift_or_failure'))
    if findings or drift:
        readout = (
            f'{findings} active Tenant Governance finding(s) and {drift} drift/failure signal(s) '
            'require review in committed evidence.'
        )
    else:
        readout = 'No active Tenant Governance finding or committed drift/failure signal is present in this reporting boundary.'

    return AnalyticsWorkbookData(
        profile=profile,
        context=context,
        metrics=metrics,
        readout=readout,
        tables=tuple(tables),
        primary_chart=None,
    )

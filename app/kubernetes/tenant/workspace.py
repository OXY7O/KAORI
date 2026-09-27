from __future__ import annotations

from typing import Any

from app.intelligence.service import get_active_recommendation_findings
from app.kubernetes.tenant.credential import build_namespace_access_package, credential_target_namespaces
from app.models.tenant import TenantAccessGrant, TenantCredential, TenantNamespace
from app.models.tenant_advanced import TenantAdvancedCapabilityIntent
from app.models.tenant_audit import TenantAuditEvidence
from app.models.tenant_managed_resource import TenantManagedResourceIntent
from app.models.tenant_policy import TenantDomainReservation, TenantExposurePolicy


def _recent(model, *, limit: int) -> list[Any]:
    return model.query.order_by(model.id.desc()).limit(limit).all()


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
        'namespace_access_rows': namespace_access_rows[:limit],
        'managed_resources': _recent(TenantManagedResourceIntent, limit=limit),
        'domain_reservations': _recent(TenantDomainReservation, limit=limit),
        'exposure_policies': _recent(TenantExposurePolicy, limit=limit),
        'audit_evidence': _recent(TenantAuditEvidence, limit=limit),
        'advanced_intents': _recent(TenantAdvancedCapabilityIntent, limit=limit),
        'tenant_governance_findings': findings[:limit],
    }

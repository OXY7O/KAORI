from __future__ import annotations

from typing import Any

from app.intelligence.service import get_active_recommendation_findings
from app.models.tenant import TenantCredential
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
    return {
        'recent_credentials': _recent(TenantCredential, limit=limit),
        'managed_resources': _recent(TenantManagedResourceIntent, limit=limit),
        'domain_reservations': _recent(TenantDomainReservation, limit=limit),
        'exposure_policies': _recent(TenantExposurePolicy, limit=limit),
        'audit_evidence': _recent(TenantAuditEvidence, limit=limit),
        'advanced_intents': _recent(TenantAdvancedCapabilityIntent, limit=limit),
        'tenant_governance_findings': findings[:limit],
    }

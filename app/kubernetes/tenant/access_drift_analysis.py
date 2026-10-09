from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.external_access_observation import latest_external_capsule_access_evidence
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantAccessGrant

_TARGET = 'kubernetes_tenant_access_drift_evidence'


def classify_tenant_access_observation(
    evidence: dict[str, Any], grants: list[TenantAccessGrant]
) -> list[dict[str, str]]:
    """Classify committed Capsule CR references; do not infer effective Kubernetes access."""
    indexed = {grant.public_id: grant for grant in grants}
    found: set[str] = set()
    findings: list[dict[str, str]] = []

    for owner in evidence.get('owners') or []:
        findings.append({
            'code': 'external_capsule_owner',
            'severity': 'warning',
            'subject': f"{owner.get('kind', 'Unknown')}/{owner.get('name', '')}",
            'action': 'Review principal identity and provider ownership; do not auto-import.',
        })

    for entry in evidence.get('bindings') or []:
        grant_id = str(entry.get('kaori_grant_id') or '').strip()
        role = str(entry.get('cluster_role_name') or '')
        if entry.get('ownership') != 'kaori' or not grant_id:
            findings.append({
                'code': 'external_access_review',
                'severity': 'warning',
                'subject': role,
                'action': 'Review Capsule source RBAC and exact principal/profile/scope mapping.',
            })
        elif grant_id not in indexed:
            findings.append({
                'code': 'orphaned_kaori_grant_marker',
                'severity': 'critical',
                'subject': grant_id,
                'action': 'Investigate stale/foreign ownership; no automatic provider delete.',
            })
        else:
            found.add(grant_id)
            grant = indexed[grant_id]
            if grant.status == 'revoked':
                findings.append({
                    'code': 'revoked_grant_still_declared',
                    'severity': 'critical',
                    'subject': grant_id,
                    'action': 'Inspect effective RoleBindings and explicitly reconcile revocation.',
                })

    for grant in grants:
        if grant.status == 'active' and grant.public_id not in found:
            findings.append({
                'code': 'active_grant_missing_capsule_declaration',
                'severity': 'warning',
                'subject': grant.public_id,
                'action': 'Inspect/reconcile committed grant; Capsule CR evidence does not prove effective RBAC.',
            })
    return findings


def latest_tenant_access_drift_evidence(tenant_id: str) -> dict[str, Any] | None:
    item = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc())
        .first()
    )
    return dict(item.metadata_json or {}) if item else None


def evaluate_tenant_access_drift_committed(*, tenant_id: str, actor_user_id: int) -> dict[str, Any]:
    """Evaluate the last explicit Capsule observation without any live Kubernetes read."""
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None or tenant.provider_key != 'capsule' or tenant.reconciliation_authority != 'capsule':
        raise ValueError('Select a governed Capsule Tenant.')
    snapshot = latest_external_capsule_access_evidence(tenant_id)
    if snapshot is None or snapshot.get('tenant_id') != tenant_id:
        raise ValueError('Collect external Capsule access evidence before analysis.')
    checked_at = datetime.fromisoformat(str(snapshot.get('observed_at') or ''))
    age = (datetime.now(UTC) - checked_at).total_seconds() if checked_at.tzinfo else -1
    if age < 0 or age > 3600:
        raise ValueError('External access evidence is stale; inspect Capsule again.')
    grants = TenantAccessGrant.query.filter_by(tenant_id=tenant_id).all()
    for grant in grants:
        updated = grant.updated_at
        if updated is not None:
            updated_utc = updated.replace(tzinfo=UTC) if updated.tzinfo is None else updated
            if updated_utc > checked_at:
                raise ValueError('Access Grants changed since Capsule observation; inspect Capsule again.')
    findings = classify_tenant_access_observation(snapshot, grants)
    result = {
        'tenant_id': tenant_id,
        'cluster_id': tenant.cluster_id,
        'status': 'review_required' if findings else 'no_declaration_findings',
        'severity': 'critical' if any(f['severity'] == 'critical' for f in findings)
        else 'warning' if findings else 'info',
        'findings': findings,
        'finding_count': len(findings),
        'observation_uid': snapshot.get('provider_uid'),
        'observation_resource_version': snapshot.get('resource_version'),
        'observation_checked_at': snapshot['observed_at'],
        'evaluated_at': datetime.now(UTC).isoformat(),
        'effective_rbac_verified': False,
        'auto_remediation_performed': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id,
        target_type=_TARGET,
        target_id=tenant_id,
        action='tenant.access_drift.evaluated',
        summary='Evaluated Capsule RBAC declarations against KAORI committed Access Grants.',
        metadata_json=result,
    ))
    db.session.commit()
    return result

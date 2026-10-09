from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.access_drift_analysis import (
    latest_tenant_access_drift_evidence,
)
from app.kubernetes.tenant.access_drift_analysis import _NATIVE_TARGET
from app.kubernetes.tenant.external_native_access_observation import latest_external_native_access_evidence
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantAccessGrant

_TARGET = 'kubernetes_tenant_access_remediation_plan'


def classify_access_remediation(
    findings: list[dict[str, str]], grants: list[TenantAccessGrant], *,
    authority_ready: bool, provider_key: str = 'capsule'
) -> list[dict[str, Any]]:
    """Map findings to existing governed actions, never execute a provider mutation."""
    active_by_public_id = {g.public_id: g for g in grants if g.status == 'active'}
    proposals: list[dict[str, Any]] = []
    for finding in findings:
        code = str(finding.get('code') or '')
        subject = str(finding.get('subject') or '')
        grant = active_by_public_id.get(subject)
        eligible = bool(
            (
                code == 'active_grant_missing_capsule_declaration' and provider_key == 'capsule'
                or code == 'active_grant_missing_native_declaration'
                and provider_key == 'native_kubernetes'
            )
            and authority_ready and grant is not None
            and grant.reconciliation_status in {'failed', 'drifted'}
        )
        proposals.append({
            'code': code,
            'subject': subject,
            'decision': 'explicit_grant_reconcile' if eligible else 'manual_review',
            'grant_id': grant.id if eligible else None,
            'reason': (
                'KAORI owns the active grant; use existing Inspect/Reconcile after operator approval.'
                if eligible else
                'Foreign/ambiguous or unverified RBAC requires human review; no automatic mutation.'
            ),
            'auto_execute': False,
        })
    return proposals


def latest_tenant_access_remediation_plan(tenant_id: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc())
        .first()
    )
    return dict(event.metadata_json or {}) if event else None


def prepare_tenant_access_remediation_plan_committed(
    *, tenant_id: str, actor_user_id: int
) -> dict[str, Any]:
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.provider_key not in {'capsule', 'native_kubernetes'}
        or tenant.lifecycle_status != 'ready'
    ):
        raise ValueError('Choose a healthy governed Native/Capsule Tenant.')
    if tenant.provider_key == 'capsule':
        evidence = latest_tenant_access_drift_evidence(tenant_id)
        target = 'kubernetes_tenant_access_drift_evidence'
    else:
        from app.kubernetes.tenant.access_drift_analysis import latest_native_access_drift_evidence
        evidence = latest_native_access_drift_evidence(tenant_id)
        target = _NATIVE_TARGET
    if not evidence or evidence.get('tenant_id') != tenant_id:
        raise ValueError('Analyze current committed Access Drift before preparing remediation.')
    captured = datetime.fromisoformat(str(evidence.get('evaluated_at') or ''))
    age = (datetime.now(UTC) - captured).total_seconds() if captured.tzinfo else -1
    if age < 0 or age > 900:
        raise ValueError('Drift evidence is stale; collect and analyze again.')
    grants = TenantAccessGrant.query.filter_by(tenant_id=tenant_id).all()
    for grant in grants:
        updated = grant.updated_at
        if updated is not None:
            updated_utc = updated.replace(tzinfo=UTC) if updated.tzinfo is None else updated
            if updated_utc > captured:
                raise ValueError('A grant changed after drift analysis; refresh evidence before remediation.')
    proposals = classify_access_remediation(
        list(evidence.get('findings') or []),
        grants,
        authority_ready=(
            tenant.provider_state == ('capsule' if tenant.provider_key == 'capsule' else 'native')
            and tenant.reconciliation_authority == tenant.provider_key
            and evidence.get('effective_rbac_verified') is False
        ),
        provider_key=tenant.provider_key,
    )
    plan = {
        'tenant_id': tenant_id,
        'cluster_id': tenant.cluster_id,
        'provider': tenant.provider_key,
        'source_target_type': target,
        'status': 'review_required' if proposals else 'nothing_to_remediate',
        'items': proposals,
        'manual_review_count': sum(x['decision'] == 'manual_review' for x in proposals),
        'explicit_reconcile_count': sum(x['decision'] == 'explicit_grant_reconcile' for x in proposals),
        'source_drift_evaluated_at': evidence['evaluated_at'],
        'prepared_at': datetime.now(UTC).isoformat(),
        'auto_mutation_performed': False,
        'execution_authority': 'existing_access_grant_inspect_reconcile_only',
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id,
        target_type=_TARGET,
        target_id=tenant_id,
        action='tenant.access_remediation.plan_prepared',
        summary='Prepared governed remediation decisions from committed Native/Capsule evidence.',
        metadata_json=plan,
    ))
    db.session.commit()
    return plan

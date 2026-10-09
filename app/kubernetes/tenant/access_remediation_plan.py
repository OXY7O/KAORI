from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.access_drift_analysis import (
    _NATIVE_TARGET,
    latest_native_access_drift_evidence,
    latest_tenant_access_drift_evidence,
)
from app.kubernetes.tenant.external_access_observation import latest_external_capsule_access_evidence
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



def require_current_remediation_source(
    evidence: dict[str, Any], *, now: datetime,
) -> datetime:
    """Fail closed if analysis outlives its authoritative provider observation."""
    try:
        evaluated = datetime.fromisoformat(str(evidence.get('evaluated_at') or ''))
        source = datetime.fromisoformat(str(
            evidence.get('source_observed_at')
            or evidence.get('observation_checked_at')
            or ''
        ))
    except ValueError as exc:
        raise ValueError('Access Drift timestamps are missing or invalid; inspect again.') from exc
    if evaluated.tzinfo is None or source.tzinfo is None:
        raise ValueError('Access Drift timestamps must contain a timezone; inspect again.')
    evaluated_utc = evaluated.astimezone(UTC)
    source_utc = source.astimezone(UTC)
    analyzed_age = (now - evaluated_utc).total_seconds()
    observed_age = (now - source_utc).total_seconds()
    if (
        analyzed_age < 0 or analyzed_age > 900
        or observed_age < 0 or observed_age > 3600
        or source_utc > evaluated_utc
    ):
        raise ValueError('Drift analysis or provider observation is stale or inconsistent; inspect again.')
    return evaluated_utc


def require_latest_remediation_observation(
    evidence: dict[str, Any], observation: dict[str, Any] | None, *,
    tenant_id: str, cluster_id: str, provider_key: str,
) -> None:
    """Require analysis to match the *newest* committed provider inventory.

    This is not a new provider read. Observing RBAC again invalidates the
    prior analysis until a new Analyze action explicitly incorporates it.
    """
    if (
        not observation
        or observation.get('tenant_id') != tenant_id
        or observation.get('cluster_id') != cluster_id
        or observation.get('provider') not in (None, provider_key)
    ):
        raise ValueError('Provider RBAC inventory is missing or changed; inspect and analyze again.')
    observed_at = observation.get('observed_at')
    analysis_source_at = (
        evidence.get('source_observed_at')
        or evidence.get('observation_checked_at')
    )
    if not observed_at or observed_at != analysis_source_at:
        raise ValueError('Newer provider RBAC inventory supersedes the analysis; analyze again.')
    if provider_key == 'native_kubernetes':
        digest = str(observation.get('evidence_sha256') or '')
        if not digest or digest != evidence.get('source_evidence_sha256'):
            raise ValueError('Native provider RBAC inventory fingerprint changed; analyze again.')
    elif (
        not observation.get('provider_uid')
        or not observation.get('resource_version')
        or observation.get('provider_uid') != evidence.get('observation_uid')
        or observation.get('resource_version') != evidence.get('observation_resource_version')
    ):
        raise ValueError('Capsule Tenant UID/resourceVersion evidence changed; analyze again.')


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
        evidence = latest_native_access_drift_evidence(tenant_id)
        target = _NATIVE_TARGET
    if (
        not evidence or evidence.get('tenant_id') != tenant_id
        or evidence.get('cluster_id') != tenant.cluster_id
    ):
        raise ValueError('Analyze current committed Access Drift before preparing remediation.')
    captured = require_current_remediation_source(evidence, now=datetime.now(UTC))
    if evidence.get('status') not in {'review_required', 'no_declaration_findings'}:
        raise ValueError('Only complete committed declaration analysis can guide remediation.')
    if evidence.get('provider') not in (None, tenant.provider_key):
        raise ValueError('Access Drift provider authority changed; analyze again.')
    observation = (
        latest_external_capsule_access_evidence(tenant_id)
        if tenant.provider_key == 'capsule'
        else latest_external_native_access_evidence(tenant_id)
    )
    require_latest_remediation_observation(
        evidence, observation, tenant_id=tenant_id,
        cluster_id=tenant.cluster_id, provider_key=tenant.provider_key,
    )
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

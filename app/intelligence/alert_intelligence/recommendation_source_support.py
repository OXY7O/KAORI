from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.extensions.db import db
from app.intelligence.recommendation_alerting import base_rule_key
from app.models.alert_ops import AlertCase, AlertCaseEvent, RecommendationAlertState, RuleException
from app.models.audit import AuditEvent
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.object_storage import ObjectStorageSystem


def _source_target(source_evidence: dict[str, Any], finding: dict[str, Any]) -> str:
    return str(
        source_evidence.get('bucket_name')
        or source_evidence.get('workload_name')
        or source_evidence.get('pod_name')
        or source_evidence.get('namespace')
        or finding.get('affected_summary')
        or finding.get('title')
        or finding.get('rule_key')
        or 'Finding'
    ).strip()


def _scope_identity(finding: dict[str, Any]) -> str:
    evidence = _finding_evidence(finding)
    return str(
        evidence.get('namespace')
        or evidence.get('bucket_id')
        or evidence.get('bucket_name')
        or evidence.get('workload_name')
        or evidence.get('phase')
        or finding.get('affected_summary')
        or '-'
    )


def _asset_key(finding: dict[str, Any]) -> str:
    evidence = _finding_evidence(finding)
    value = evidence.get('asset_key') or evidence.get('cluster_id') or evidence.get('object_storage_system_id')
    return str(value or 'unknown')


def _case_asset_type(
    finding: dict[str, Any],
    *,
    domain: str,
    grouping_mode: str,
    grouped_asset_types: dict[str, str],
) -> str:
    if grouping_mode == 'rule_asset':
        return grouped_asset_types.get(str(domain or '').strip().lower(), 'asset')
    return str(finding.get('source_kind') or 'resource')


def _asset_name(finding: dict[str, Any], *, domain: str, asset_key: str) -> str:
    evidence = _finding_evidence(finding)
    explicit = evidence.get('system_name') or evidence.get('cluster_name')
    if explicit:
        return str(explicit)
    if domain == 'kubernetes' and asset_key != 'unknown':
        cluster = db.session.get(Cluster, asset_key)
        if cluster is not None:
            return str(cluster.name)
    if domain == 'object_storage' and asset_key != 'unknown':
        try:
            system = db.session.get(ObjectStorageSystem, int(asset_key))
        except (TypeError, ValueError):
            system = None
        if system is not None:
            return str(system.name)
    return str(finding.get('domain_label') or domain.replace('_', ' ').title())


def _namespace(finding: dict[str, Any]) -> str | None:
    evidence = _finding_evidence(finding)
    return _optional_text(evidence.get('namespace'))


def _observe_finding(
    finding: dict[str, Any],
    *,
    policy: dict[str, Any],
    now: datetime,
    grouping_fingerprint: Callable[..., str],
) -> RecommendationAlertState:
    finding_key = str(finding.get('rule_key') or '').strip()
    rule_key = base_rule_key(finding_key)
    asset_key = _asset_key(finding)
    namespace = _namespace(finding)
    fingerprint = grouping_fingerprint(
        finding,
        rule_key=rule_key,
        asset_key=asset_key,
        namespace=namespace,
        grouping_mode=str(policy['grouping_mode']),
    )
    state = RecommendationAlertState.query.filter_by(finding_key=finding_key).first()
    evidence_hash = _evidence_hash(finding)
    if state is None:
        state = RecommendationAlertState()
        state.finding_key = finding_key
        state.rule_key = rule_key
        state.domain = str(finding.get('domain') or 'unknown')
        state.asset_key = asset_key
        state.namespace = namespace
        state.grouping_fingerprint = fingerprint
        state.active = True
        state.occurrence_count = 1
        state.first_seen_at = now
        state.last_seen_at = now
        state.evidence_hash = evidence_hash
        db.session.add(state)
        db.session.flush()
        return state
    if not state.active:
        state.active = True
        state.cleared_at = None
        state.first_seen_at = now
        state.occurrence_count = 1
        state.alert_case_id = None
        state.promotion_suppressed_until_clear = False
        state.promotion_suppression_reason = None
    else:
        state.occurrence_count = int(state.occurrence_count or 0) + 1
    state.rule_key = rule_key
    state.domain = str(finding.get('domain') or state.domain)
    state.asset_key = asset_key
    state.namespace = namespace
    state.grouping_fingerprint = fingerprint
    state.last_seen_at = now
    state.evidence_hash = evidence_hash
    return state


def _evidence_hash(finding: dict[str, Any]) -> str:
    payload = {
        'rule_key': finding.get('rule_key'),
        'severity': finding.get('severity'),
        'summary': finding.get('summary'),
        'condition_summary': finding.get('condition_summary'),
        'evidence': _finding_evidence(finding),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _severity_rank(value: str) -> int:
    return {'unknown': 0, 'info': 1, 'warning': 2, 'critical': 3}.get(str(value or '').lower(), 0)


def _severity(value: Any) -> str:
    normalized = str(value or 'info').strip().lower()
    return normalized if normalized in {'critical', 'warning', 'info'} else 'info'


def _timeline(
    case: AlertCase,
    event_type: str,
    summary: str,
    *,
    actor_user_id: int | None,
    metadata: dict[str, Any],
) -> None:
    row = AlertCaseEvent()
    row.case_id = case.id
    row.event_type = event_type
    row.actor_user_id = actor_user_id
    row.summary = summary[:500]
    row.metadata_json = metadata
    db.session.add(row)


def _audit_promotion(case: AlertCase, *, actor_user_id: int | None, automatic: bool) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'alert_intelligence'
    event.target_id = case.public_id
    event.action = 'recommendation_alert_auto_promoted' if automatic else 'recommendation_alert_promoted'
    event.summary = (
        'Recommendation automatically escalated into Alert Operations.'
        if automatic
        else 'Recommendation manually promoted into Alert Operations.'
    )
    event.metadata_json = {
        'module': 'Alert Intelligence',
        'case_id': case.public_id,
        'recommendation_key': case.source_ref,
        'rule_key': case.rule_key,
        'domain': case.domain,
        'asset_key': case.asset_key,
    }
    db.session.add(event)


def _finding_evidence(finding: dict[str, Any]) -> dict[str, Any]:
    raw = finding.get('evidence')
    if not isinstance(raw, dict):
        return {}
    return {str(key): value for key, value in raw.items()}


def _optional_text(value: Any) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None


def _binding_posture(integration_type: str, asset_type: str, asset_key: str) -> tuple[bool, str]:
    binding = (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationInstance.integration_type == integration_type,
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
            IntegrationBinding.asset_type == asset_type,
            IntegrationBinding.asset_key == asset_key,
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc())
        .first()
    )
    return (True, '') if binding is not None else (False, 'source_unavailable')


def _source_unknown_summary(reason: str) -> str:
    if reason == 'source_deleted':
        return 'The monitored source was deleted. KAORI cannot assert firing or resolution without fresh evidence.'
    return 'The monitored source is unavailable or not ready. KAORI is holding the alert as Unknown until fresh evidence returns.'


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _record_accepted_risk_source(
    case: AlertCase,
    finding: dict[str, Any],
    *,
    exception: RuleException,
) -> None:
    evidence = dict(case.evidence_json or {})
    raw = evidence.get('accepted_risk_sources')
    rows = list(raw) if isinstance(raw, list) else []
    finding_key = str(finding.get('rule_key') or '')
    if not any(isinstance(row, dict) and row.get('finding_key') == finding_key for row in rows):
        source_evidence = _finding_evidence(finding)
        rows.append(
            {
                'finding_key': finding_key,
                'target': _source_target(source_evidence, finding),
                'exception_public_id': exception.public_id,
                'risk_reference': exception.risk_reference or '',
            }
        )
    evidence['accepted_risk_sources'] = rows
    evidence['accepted_risk_count'] = len(rows)
    evidence['accepted_risk_exception'] = exception.public_id
    evidence['accepted_risk_reference'] = exception.risk_reference or ''
    case.evidence_json = evidence


def _automatic_promotion_threshold_reached(
    *,
    first_seen_at: datetime,
    occurrence_count: int,
    policy: dict[str, Any],
    now: datetime,
    observed_severity: str,
) -> bool:
    stable_for = now - _as_utc(first_seen_at)
    if str(observed_severity or '').strip().lower() == 'critical':
        return stable_for >= timedelta(minutes=int(policy.get('critical_stability_window_minutes', 0))) and (
            occurrence_count >= int(policy.get('critical_minimum_occurrences', 1))
        )
    return stable_for >= timedelta(minutes=int(policy['stability_window_minutes'])) and (
        occurrence_count >= int(policy['minimum_occurrences'])
    )

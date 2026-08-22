from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.extensions.db import db
from app.intelligence.alert_intelligence.lifecycle import (
    mark_case_source_resolved,
    mark_case_source_unknown,
    restore_case_source_firing,
    set_case_policy_routing_eligibility,
)
from app.intelligence.recommendation_alerting import base_rule_key, catalog_rule, effective_alert_policy
from app.intelligence.service import get_active_recommendation_findings
from app.models.alert_ops import AlertCase, AlertCaseEvent, RecommendationAlertState
from app.models.audit import AuditEvent
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.object_storage import ObjectStorageSystem


def reconcile_recommendation_alert_cases() -> dict[str, int]:
    """Evaluate fresh recommendation findings into governed Alert Operations cases.

    Missing findings only resolve cases when the underlying source is fresh. Source loss
    transitions the case to Unknown so stale data can never masquerade as recovery.
    """

    now = datetime.now(UTC)
    findings = get_active_recommendation_findings()
    fresh_keys: set[str] = set()
    stats = {
        'observed': 0,
        'eligible': 0,
        'promoted': 0,
        'updated': 0,
        'resolved': 0,
        'source_unknown': 0,
        'skipped': 0,
    }
    for finding in findings:
        finding_key = str(finding.get('rule_key') or '').strip()
        if not finding_key:
            stats['skipped'] += 1
            continue
        available, source_reason = _source_evidence_posture_for_finding(finding)
        if not available:
            state = RecommendationAlertState.query.filter_by(finding_key=finding_key).first()
            if state is not None and state.alert_case_id is not None:
                case = db.session.get(AlertCase, state.alert_case_id)
                if case is not None and case.workflow_state != 'closed':
                    changed = mark_case_source_unknown(
                        case,
                        reason=source_reason,
                        source_summary=_source_unknown_summary(source_reason),
                        now=now,
                        metadata={'recommendation_key': finding_key},
                    )
                    stats['source_unknown'] += int(changed)
            stats['skipped'] += 1
            continue

        fresh_keys.add(finding_key)
        policy = effective_alert_policy(
            base_rule_key(finding_key), observed_severity=str(finding.get('severity') or 'info')
        )
        state = _observe_finding(finding, policy=policy, now=now)
        stats['observed'] += 1
        case = db.session.get(AlertCase, state.alert_case_id) if state.alert_case_id is not None else None

        if not policy['eligible']:
            if case is not None and case.workflow_state != 'closed':
                if not policy.get('severity_eligible', True):
                    mark_case_source_resolved(
                        case,
                        now=now,
                        source_summary=(
                            'The recommendation remains active, but its severity dropped below the '
                            'Rule Catalog alert-escalation threshold.'
                        ),
                        auto_resolution_summary='The recommendation de-escalated below the alerting severity floor.',
                        auto_remediation_step='Observed the recommendation severity return below the alerting threshold.',
                        auto_verification_evidence=(
                            'Rule Catalog severity evaluation no longer classifies this condition as alert-eligible.'
                        ),
                    )
                    stats['resolved'] += 1
                else:
                    _refresh_case_from_finding(case, finding, now=now)
                    set_case_policy_routing_eligibility(case, eligible=False, now=now)
                    stats['updated'] += 1
            continue

        stats['eligible'] += 1
        if case is not None and case.workflow_state != 'closed':
            _refresh_case_from_finding(case, finding, now=now)
            set_case_policy_routing_eligibility(case, eligible=True, now=now)
            stats['updated'] += 1
            continue
        if state.promotion_suppressed_until_clear:
            stats['skipped'] += 1
            continue
        if policy['mode'] != 'automatic' or not _automatic_threshold_reached(
            state, policy=policy, now=now, observed_severity=str(finding.get('severity') or 'info')
        ):
            continue
        _ensure_alert_case(finding, state=state, policy=policy, actor_user_id=None, now=now, automatic=True)
        stats['promoted'] += 1

    for state in RecommendationAlertState.query.filter_by(active=True).all():
        if state.finding_key in fresh_keys:
            continue
        available, source_reason = _source_evidence_posture_for_state(state)
        case = db.session.get(AlertCase, state.alert_case_id) if state.alert_case_id else None
        if not available:
            if case is not None and case.workflow_state != 'closed':
                changed = mark_case_source_unknown(
                    case,
                    reason=source_reason,
                    source_summary=_source_unknown_summary(source_reason),
                    now=now,
                    metadata={'recommendation_key': state.finding_key},
                )
                stats['source_unknown'] += int(changed)
            continue

        state.active = False
        state.cleared_at = now
        state.promotion_suppressed_until_clear = False
        state.promotion_suppression_reason = None
        if case is None or case.source_state == 'resolved':
            continue
        db.session.flush()
        other_active = RecommendationAlertState.query.filter(
            RecommendationAlertState.alert_case_id == case.id,
            RecommendationAlertState.active.is_(True),
        ).first()
        if other_active is not None:
            continue
        mark_case_source_resolved(
            case,
            now=now,
            source_summary='The originating KAORI recommendation cleared from fresh committed evidence.',
            auto_resolution_summary='The originating KAORI recommendation cleared without recorded manual remediation.',
            auto_remediation_step='Observed the recommendation clear after a fresh committed evidence refresh.',
            auto_verification_evidence='The recommendation was absent from the latest fresh Intelligence evaluation.',
        )
        stats['resolved'] += 1
    db.session.commit()
    return stats


def promote_recommendation_to_alert(
    finding: dict[str, Any],
    *,
    actor_user_id: int | None,
) -> AlertCase:
    """Manually promote one active recommendation into the shared Alert Operations lifecycle."""

    finding_key = str(finding.get('rule_key') or '').strip()
    if not finding_key:
        raise ValueError('The recommendation does not expose a stable finding key.')
    policy = effective_alert_policy(
        base_rule_key(finding_key), observed_severity=str(finding.get('severity') or 'info')
    )
    if not policy['eligible']:
        raise ValueError(
            'This rule is configured as Recommendation Only. Enable Alert Escalation in Rule Catalog first.'
        )
    now = datetime.now(UTC)
    available, source_reason = _source_evidence_posture_for_finding(finding)
    if not available:
        raise ValueError(_source_unknown_summary(source_reason))
    state = _observe_finding(finding, policy=policy, now=now)
    state.promotion_suppressed_until_clear = False
    state.promotion_suppression_reason = None
    case = _ensure_alert_case(
        finding,
        state=state,
        policy=policy,
        actor_user_id=actor_user_id,
        now=now,
        automatic=False,
    )
    return case


def _observe_finding(
    finding: dict[str, Any],
    *,
    policy: dict[str, Any],
    now: datetime,
) -> RecommendationAlertState:
    finding_key = str(finding.get('rule_key') or '').strip()
    rule_key = base_rule_key(finding_key)
    asset_key = _asset_key(finding)
    namespace = _namespace(finding)
    fingerprint = _grouping_fingerprint(
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


def _automatic_threshold_reached(
    state: RecommendationAlertState,
    *,
    policy: dict[str, Any],
    now: datetime,
    observed_severity: str,
) -> bool:
    first_seen = _as_utc(state.first_seen_at)
    stable_for = now - first_seen
    if str(observed_severity or '').strip().lower() == 'critical':
        return (
            stable_for >= timedelta(minutes=int(policy.get('critical_stability_window_minutes', 0)))
            and int(state.occurrence_count or 0) >= int(policy.get('critical_minimum_occurrences', 1))
        )
    return stable_for >= timedelta(minutes=int(policy['stability_window_minutes'])) and int(
        state.occurrence_count or 0
    ) >= int(policy['minimum_occurrences'])


def _ensure_alert_case(
    finding: dict[str, Any],
    *,
    state: RecommendationAlertState,
    policy: dict[str, Any],
    actor_user_id: int | None,
    now: datetime,
    automatic: bool,
) -> AlertCase:
    case_key = f'recommendation:{state.grouping_fingerprint}'[:96]
    case = (
        AlertCase.query.filter(
            AlertCase.case_key == case_key,
            AlertCase.workflow_state != 'closed',
        )
        .order_by(AlertCase.id.desc())
        .first()
    )
    created = case is None
    if case is None:
        case = AlertCase()
        case.case_key = case_key
        case.fingerprint = state.grouping_fingerprint
        case.source_type = 'recommendation'
        case.source_ref = state.finding_key
        case.rule_key = state.rule_key
        case.domain = state.domain
        case.asset_type = str(finding.get('source_kind') or 'resource')
        case.asset_key = state.asset_key
        case.asset_name = _asset_name(finding, domain=state.domain, asset_key=state.asset_key)
        case.alert_name = str(finding.get('title') or finding.get('list_title') or state.rule_key)[:255]
        case.severity = _severity(finding.get('severity'))
        case.source_state = 'firing'
        case.workflow_state = 'open'
        case.first_seen_at = state.first_seen_at or now
        case.last_seen_at = now
        db.session.add(case)
        db.session.flush()
        _timeline(
            case,
            'recommendation_promoted',
            (
                'Recommendation automatically escalated after satisfying the configured stability policy.'
                if automatic
                else 'Recommendation manually promoted into Alert Operations by an operator.'
            ),
            actor_user_id=actor_user_id,
            metadata={
                'recommendation_key': state.finding_key,
                'rule_key': state.rule_key,
                'policy_mode': policy['mode'],
                'stability_window_minutes': policy['stability_window_minutes'],
                'minimum_occurrences': policy['minimum_occurrences'],
                'promotion_mode': 'automatic' if automatic else 'manual',
            },
        )
        case.evidence_json = {
            **dict(case.evidence_json or {}),
            'promotion_mode': 'automatic' if automatic else 'manual',
        }
        _audit_promotion(case, actor_user_id=actor_user_id, automatic=automatic)
    _refresh_case_from_finding(case, finding, now=now)
    state.alert_case_id = case.id
    if not created:
        _attach_recommendation_source(case, finding)
    return case


def _refresh_case_from_finding(case: AlertCase, finding: dict[str, Any], *, now: datetime) -> None:
    finding_key = str(finding.get('rule_key') or '').strip()
    previous_source_state = case.source_state
    if finding_key:
        case.source_ref = finding_key
    case.last_seen_at = now
    if previous_source_state == 'unknown':
        restore_case_source_firing(
            case,
            source_summary='Fresh source evidence is available again and confirms the recommendation is still active.',
            now=now,
        )
    else:
        case.source_state = 'firing'
        case.source_state_reason = None
        case.source_state_changed_at = now
        case.source_resolved_at = None
    if previous_source_state == 'resolved' and case.workflow_state != 'closed':
        case.workflow_state = 'open'
        case.verification_started_at = None
        _timeline(
            case,
            'recommendation_source_reopened',
            'The originating recommendation became active again before case closure.',
            actor_user_id=None,
            metadata={'recommendation_key': case.source_ref, 'rule_key': case.rule_key},
        )
    next_severity = _severity(finding.get('severity'))
    previous_severity = case.severity
    if previous_severity and previous_severity != next_severity:
        case.previous_severity = previous_severity
        case.severity_changed_at = now
        event_type = 'severity_escalated' if _severity_rank(next_severity) > _severity_rank(previous_severity) else 'severity_deescalated'
        if event_type == 'severity_escalated' and case.acknowledgement_expires_at is not None:
            # A higher severity is a new paging condition; an ACK at the old severity cannot suppress it.
            case.acknowledgement_expires_at = now
        _timeline(
            case,
            event_type,
            f'Alert severity changed from {previous_severity.title()} to {next_severity.title()}.',
            actor_user_id=None,
            metadata={'previous_severity': previous_severity, 'current_severity': next_severity},
        )
    case.severity = next_severity
    case.summary = str(finding.get('summary') or finding.get('condition_summary') or '').strip() or None
    evidence = finding.get('evidence') if isinstance(finding.get('evidence'), dict) else {}
    case.namespace = _optional_text(evidence.get('namespace'))
    case.target = _optional_text(
        evidence.get('bucket_name')
        or evidence.get('workload_name')
        or evidence.get('pod_name')
        or finding.get('affected_summary')
    )
    labels = dict(case.labels_json or {})
    labels.update(
        {
            'source_type': 'recommendation',
            'rule_key': base_rule_key(str(finding.get('rule_key') or '')),
            'recommendation_key': str(finding.get('rule_key') or ''),
            'category': str(finding.get('category') or ''),
            'priority': str(finding.get('priority') or ''),
            'signal_source': str(finding.get('signal_source') or ''),
        }
    )
    case.labels_json = labels
    _attach_recommendation_source(case, finding)


def _attach_recommendation_source(case: AlertCase, finding: dict[str, Any]) -> None:
    evidence = dict(case.evidence_json or {})
    sources = dict(evidence.get('recommendation_sources') or {})
    key = str(finding.get('rule_key') or '')
    source_evidence = finding.get('evidence') if isinstance(finding.get('evidence'), dict) else {}
    sources[key] = {
        'title': str(finding.get('title') or ''),
        'summary': str(finding.get('summary') or ''),
        'condition_summary': str(finding.get('condition_summary') or ''),
        'recommended_action': str(finding.get('recommended_action') or ''),
        'affected_summary': str(finding.get('affected_summary') or ''),
        'evidence': dict(source_evidence),
    }
    evidence.update(
        {
            'summary': case.summary,
            'source': 'KAORI Recommendation',
            'source_type': 'recommendation',
            'rule_key': base_rule_key(key),
            'recommendation_key': case.source_ref or key,
            'recommendation_sources': sources,
            'recommendation_count': len(sources),
        }
    )
    case.evidence_json = evidence


def _grouping_fingerprint(
    finding: dict[str, Any],
    *,
    rule_key: str,
    asset_key: str,
    namespace: str | None,
    grouping_mode: str,
) -> str:
    if grouping_mode == 'rule_asset':
        raw = '|'.join((rule_key, asset_key))
    elif grouping_mode == 'rule_asset_scope':
        raw = '|'.join((rule_key, asset_key, namespace or _scope_identity(finding)))
    else:
        raw = '|'.join((rule_key, asset_key, str(finding.get('rule_key') or '')))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:64]


def _scope_identity(finding: dict[str, Any]) -> str:
    evidence = finding.get('evidence') if isinstance(finding.get('evidence'), dict) else {}
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
    evidence = finding.get('evidence') if isinstance(finding.get('evidence'), dict) else {}
    value = evidence.get('asset_key') or evidence.get('cluster_id') or evidence.get('object_storage_system_id')
    return str(value or 'unknown')


def _asset_name(finding: dict[str, Any], *, domain: str, asset_key: str) -> str:
    evidence = finding.get('evidence') if isinstance(finding.get('evidence'), dict) else {}
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
    evidence = finding.get('evidence') if isinstance(finding.get('evidence'), dict) else {}
    return _optional_text(evidence.get('namespace'))


def _evidence_hash(finding: dict[str, Any]) -> str:
    payload = {
        'rule_key': finding.get('rule_key'),
        'severity': finding.get('severity'),
        'summary': finding.get('summary'),
        'condition_summary': finding.get('condition_summary'),
        'evidence': finding.get('evidence') if isinstance(finding.get('evidence'), dict) else {},
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


def _optional_text(value: Any) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None


def _source_evidence_posture_for_finding(finding: dict[str, Any]) -> tuple[bool, str]:
    evidence = finding.get('evidence') if isinstance(finding.get('evidence'), dict) else {}
    asset_key = str(
        evidence.get('asset_key')
        or evidence.get('cluster_id')
        or evidence.get('object_storage_system_id')
        or ''
    ).strip()
    return _source_evidence_posture(
        domain=str(finding.get('domain') or ''),
        asset_key=asset_key,
        signal_source=str(finding.get('signal_source') or ''),
    )


def _source_evidence_posture_for_state(state: RecommendationAlertState) -> tuple[bool, str]:
    rule = catalog_rule(state.rule_key) or {}
    return _source_evidence_posture(
        domain=state.domain,
        asset_key=state.asset_key,
        signal_source=str(rule.get('signal_source') or ''),
    )


def _source_evidence_posture(*, domain: str, asset_key: str, signal_source: str) -> tuple[bool, str]:
    normalized_domain = str(domain or '').strip().lower()
    normalized_asset = str(asset_key or '').strip()
    signal = str(signal_source or '').strip().lower()
    if not normalized_asset:
        return True, ''
    if normalized_domain == 'kubernetes':
        asset = db.session.get(Cluster, normalized_asset)
        if asset is None:
            return False, 'source_deleted'
        if signal == 'alertmanager':
            return _binding_posture('alert_source', 'kubernetes_cluster', normalized_asset)
        if signal in {'metrics_source', 'prometheus'}:
            return _binding_posture('metrics_source', 'kubernetes_cluster', normalized_asset)
        return (True, '') if str(asset.status or '').lower() == 'connected' else (False, 'source_unavailable')
    if normalized_domain == 'object_storage':
        asset = db.session.get(ObjectStorageSystem, normalized_asset)
        if asset is None:
            return False, 'source_deleted'
        if signal in {'metrics_source', 'prometheus'}:
            return _binding_posture('metrics_source', 'object_storage_system', normalized_asset)
        if signal == 'alertmanager':
            return _binding_posture('alert_source', 'object_storage_system', normalized_asset)
        return (True, '') if str(asset.status or '').lower() == 'connected' else (False, 'source_unavailable')
    return True, ''


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
    return ((True, '') if binding is not None else (False, 'source_unavailable'))


def _source_unknown_summary(reason: str) -> str:
    if reason == 'source_deleted':
        return 'The monitored source was deleted. KAORI cannot assert firing or resolution without fresh evidence.'
    return 'The monitored source is unavailable or not ready. KAORI is holding the alert as Unknown until fresh evidence returns.'


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.intelligence.alert_intelligence.case_state import (
    close_accepted_risk_alert,
    mark_case_source_unknown,
    restore_case_source_firing,
    set_case_policy_routing_eligibility,
    supersede_recommendation_alert,
)
from app.intelligence.alert_intelligence.lifecycle import mark_case_source_resolved
from app.intelligence.alert_intelligence.recommendation_source_support import (
    _as_utc,
    _asset_name,
    _audit_promotion,
    _automatic_promotion_threshold_reached,
    _binding_posture,
    _case_asset_type,
    _finding_evidence,
    _observe_finding,
    _optional_text,
    _record_accepted_risk_source,
    _scope_identity,
    _severity,
    _severity_rank,
    _source_target,
    _source_unknown_summary,
    _timeline,
)
from app.intelligence.alert_signals.service import alert_signal_source_posture
from app.intelligence.recommendation_alerting import base_rule_key, catalog_rule, effective_alert_policy
from app.intelligence.rule_exceptions import active_rule_exceptions, matching_rule_exception
from app.intelligence.service import get_active_recommendation_findings
from app.models.alert_ops import AlertCase, RecommendationAlertState, RuleException
from app.models.cluster import Cluster
from app.models.object_storage import ObjectStorageSystem

_GROUPED_ASSET_TYPES = {'kubernetes': 'kubernetes_cluster', 'object_storage': 'object_storage_system'}


def reconcile_recommendation_alert_cases() -> dict[str, int]:
    """Evaluate fresh findings while preserving Unknown state when source evidence is unavailable."""

    now = datetime.now(UTC)
    findings = get_active_recommendation_findings()
    fresh_keys: set[str] = set()
    active_exceptions = active_rule_exceptions(
        {base_rule_key(str(finding.get('rule_key') or '')) for finding in findings},
        now=now,
    )
    stats = {
        'observed': 0,
        'eligible': 0,
        'promoted': 0,
        'updated': 0,
        'resolved': 0,
        'source_unknown': 0,
        'accepted_risk': 0,
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
        state = _observe_finding(finding, policy=policy, now=now, grouping_fingerprint=_grouping_fingerprint)
        stats['observed'] += 1
        case = db.session.get(AlertCase, state.alert_case_id) if state.alert_case_id is not None else None
        case = _rehome_state_for_grouping(state, case=case, now=now)
        exception = matching_rule_exception(finding, rows=active_exceptions, now=now)
        if exception is not None:
            _apply_rule_exception_to_state(
                finding,
                state=state,
                case=case,
                exception=exception,
                policy=policy,
                now=now,
            )
            stats['accepted_risk'] += 1
            continue
        if state.rule_exception_id is not None:
            state.rule_exception_id = None
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
                    _refresh_case_from_finding(
                        case,
                        finding,
                        now=now,
                        grouping_mode=str(policy['grouping_mode']),
                    )
                    set_case_policy_routing_eligibility(case, eligible=False, now=now)
                    stats['updated'] += 1
            continue

        stats['eligible'] += 1
        if case is not None and case.workflow_state != 'closed':
            _refresh_case_from_finding(
                case,
                finding,
                now=now,
                grouping_mode=str(policy['grouping_mode']),
            )
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

    _reconcile_missing_recommendation_states(fresh_keys=fresh_keys, now=now, stats=stats)
    db.session.commit()
    return stats


def _reconcile_missing_recommendation_states(
    *,
    fresh_keys: set[str],
    now: datetime,
    stats: dict[str, int],
) -> None:
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
        state.rule_exception_id = None
        if case is None or case.source_state == 'resolved':
            continue
        db.session.flush()
        other_active = RecommendationAlertState.query.filter(
            RecommendationAlertState.alert_case_id == case.id,
            RecommendationAlertState.active.is_(True),
        ).first()
        if other_active is not None:
            policy = effective_alert_policy(state.rule_key)
            state.alert_case_id = None
            _remove_recommendation_source(
                case,
                state.finding_key,
                grouping_mode=str(policy.get('grouping_mode') or 'finding'),
                now=now,
            )
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
    exception = matching_rule_exception(finding, now=now)
    if exception is not None:
        reference = str(exception.risk_reference or exception.public_id)
        raise ValueError(
            f'This recommendation is covered by accepted risk {reference} until '
            f'{_as_utc(exception.expires_at).date().isoformat()}.'
        )
    state = _observe_finding(finding, policy=policy, now=now, grouping_fingerprint=_grouping_fingerprint)
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


def _automatic_threshold_reached(
    state: RecommendationAlertState,
    *,
    policy: dict[str, Any],
    now: datetime,
    observed_severity: str,
) -> bool:
    return _automatic_promotion_threshold_reached(
        first_seen_at=state.first_seen_at,
        occurrence_count=int(state.occurrence_count or 0),
        policy=policy,
        now=now,
        observed_severity=observed_severity,
    )


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
    if case is None:
        case = AlertCase()
        case.case_key = case_key
        case.fingerprint = state.grouping_fingerprint
        case.source_type = 'recommendation'
        case.source_ref = state.finding_key
        case.rule_key = state.rule_key
        case.domain = state.domain
        case.asset_type = _case_asset_type(
            finding,
            domain=state.domain,
            grouping_mode=str(policy['grouping_mode']),
            grouped_asset_types=_GROUPED_ASSET_TYPES,
        )
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
    _refresh_case_from_finding(
        case,
        finding,
        now=now,
        grouping_mode=str(policy['grouping_mode']),
    )
    state.alert_case_id = case.id
    return case


def _rehome_state_for_grouping(
    state: RecommendationAlertState,
    *,
    case: AlertCase | None,
    now: datetime,
) -> AlertCase | None:
    if case is None:
        return None
    desired_case_key = f'recommendation:{state.grouping_fingerprint}'[:96]
    if case.case_key == desired_case_key:
        return case
    state.alert_case_id = None
    if case.workflow_state == 'closed':
        return None
    db.session.flush()
    remaining = RecommendationAlertState.query.filter(
        RecommendationAlertState.alert_case_id == case.id,
        RecommendationAlertState.active.is_(True),
    ).first()
    if remaining is None:
        supersede_recommendation_alert(
            case,
            reason=(
                f'Rule Catalog grouping changed from {case.case_key} to {desired_case_key}; '
                'the active finding will be attached to the new grouped AlertCase identity.'
            ),
            now=now,
        )
    else:
        previous_grouping = str((case.labels_json or {}).get('grouping_mode') or 'finding')
        _remove_recommendation_source(
            case,
            state.finding_key,
            grouping_mode=previous_grouping,
            now=now,
        )
    return None


def apply_rule_exception_to_active_findings(
    exception: RuleException,
    findings: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Apply a newly created exception immediately to already observed recommendation states."""

    current = now or datetime.now(UTC)
    stats = {'covered': 0, 'detached': 0, 'cases_closed': 0}
    for finding in findings:
        if matching_rule_exception(finding, rows=[exception], now=current) is None:
            continue
        stats['covered'] += 1
        finding_key = str(finding.get('rule_key') or '').strip()
        state = RecommendationAlertState.query.filter_by(finding_key=finding_key, active=True).first()
        if state is None:
            continue
        case = db.session.get(AlertCase, state.alert_case_id) if state.alert_case_id is not None else None
        policy = effective_alert_policy(
            base_rule_key(finding_key),
            observed_severity=str(finding.get('severity') or 'info'),
        )
        closed = _apply_rule_exception_to_state(
            finding,
            state=state,
            case=case,
            exception=exception,
            policy=policy,
            now=current,
        )
        stats['detached'] += int(case is not None and state.alert_case_id is None)
        stats['cases_closed'] += int(closed)
    return stats


def _apply_rule_exception_to_state(
    finding: dict[str, Any],
    *,
    state: RecommendationAlertState,
    case: AlertCase | None,
    exception: RuleException,
    policy: dict[str, Any],
    now: datetime,
) -> bool:
    state.rule_exception_id = exception.id
    if case is None:
        return False
    _record_accepted_risk_source(case, finding, exception=exception)
    state.alert_case_id = None
    if case.workflow_state == 'closed':
        return False
    db.session.flush()
    remaining = RecommendationAlertState.query.filter(
        RecommendationAlertState.alert_case_id == case.id,
        RecommendationAlertState.active.is_(True),
    ).first()
    if remaining is None:
        _remove_recommendation_source(
            case,
            str(finding.get('rule_key') or state.finding_key),
            grouping_mode=str(policy.get('grouping_mode') or 'finding'),
            now=now,
        )
        accepted_count = int((case.evidence_json or {}).get('accepted_risk_count') or 1)
        case.summary = (
            f'{accepted_count} active recommendation finding'
            f'{"s" if accepted_count != 1 else ""} are covered by time-bounded accepted risk.'
        )
        case.target = f'{accepted_count} accepted-risk finding' + ('s' if accepted_count != 1 else '')
        close_accepted_risk_alert(
            case,
            exception_public_id=exception.public_id,
            exception_reason=exception.reason,
            risk_reference=exception.risk_reference,
            actor_user_id=exception.created_by_user_id,
            now=now,
        )
        return True
    _remove_recommendation_source(
        case,
        str(finding.get('rule_key') or state.finding_key),
        grouping_mode=str(policy.get('grouping_mode') or 'finding'),
        now=now,
    )
    return False


def _remove_accepted_risk_source(case: AlertCase, finding_key: str) -> None:
    evidence = dict(case.evidence_json or {})
    raw = evidence.get('accepted_risk_sources')
    if not isinstance(raw, list):
        return
    normalized_key = str(finding_key or '')
    rows = [row for row in raw if not (isinstance(row, dict) and str(row.get('finding_key') or '') == normalized_key)]
    if len(rows) == len(raw):
        return
    if rows:
        evidence['accepted_risk_sources'] = rows
        evidence['accepted_risk_count'] = len(rows)
        latest = next((row for row in reversed(rows) if isinstance(row, dict)), {})
        evidence['accepted_risk_exception'] = str(latest.get('exception_public_id') or '')
        evidence['accepted_risk_reference'] = str(latest.get('risk_reference') or '')
    else:
        evidence.pop('accepted_risk_sources', None)
        evidence.pop('accepted_risk_count', None)
        evidence.pop('accepted_risk_exception', None)
        evidence.pop('accepted_risk_reference', None)
    case.evidence_json = evidence


def _refresh_case_from_finding(
    case: AlertCase,
    finding: dict[str, Any],
    *,
    now: datetime,
    grouping_mode: str = 'finding',
) -> None:
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
    evidence = _finding_evidence(finding)
    if grouping_mode == 'finding':
        _apply_case_severity(case, next_severity, now=now)
        case.summary = str(finding.get('summary') or finding.get('condition_summary') or '').strip() or None
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
            'grouping_mode': grouping_mode,
        }
    )
    case.labels_json = labels
    _attach_recommendation_source(case, finding)
    if grouping_mode != 'finding':
        _refresh_grouped_case(case, grouping_mode=grouping_mode, now=now)


def _apply_case_severity(case: AlertCase, next_severity: str, *, now: datetime) -> None:
    previous_severity = case.severity
    if previous_severity and previous_severity != next_severity:
        case.previous_severity = previous_severity
        case.severity_changed_at = now
        event_type = (
            'severity_escalated'
            if _severity_rank(next_severity) > _severity_rank(previous_severity)
            else 'severity_deescalated'
        )
        if event_type == 'severity_escalated' and case.acknowledgement_expires_at is not None:
            case.acknowledgement_expires_at = now
        _timeline(
            case,
            event_type,
            f'Alert severity changed from {previous_severity.title()} to {next_severity.title()}.',
            actor_user_id=None,
            metadata={'previous_severity': previous_severity, 'current_severity': next_severity},
        )
    case.severity = next_severity


def _attach_recommendation_source(case: AlertCase, finding: dict[str, Any]) -> None:
    finding_key = str(finding.get('rule_key') or '')
    _remove_accepted_risk_source(case, finding_key)
    evidence = dict(case.evidence_json or {})
    raw_sources = evidence.get('recommendation_sources')
    sources: dict[str, Any] = (
        {str(source_key): value for source_key, value in raw_sources.items()} if isinstance(raw_sources, dict) else {}
    )
    key = finding_key
    source_evidence = _finding_evidence(finding)
    sources[key] = {
        'title': str(finding.get('title') or ''),
        'summary': str(finding.get('summary') or ''),
        'condition_summary': str(finding.get('condition_summary') or ''),
        'recommended_action': str(finding.get('recommended_action') or ''),
        'affected_summary': str(finding.get('affected_summary') or ''),
        'severity': _severity(finding.get('severity')),
        'target': _source_target(source_evidence, finding),
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


def _remove_recommendation_source(
    case: AlertCase,
    finding_key: str,
    *,
    grouping_mode: str,
    now: datetime,
) -> None:
    evidence = dict(case.evidence_json or {})
    raw_sources = evidence.get('recommendation_sources')
    if not isinstance(raw_sources, dict):
        return
    sources = {str(key): value for key, value in raw_sources.items()}
    sources.pop(str(finding_key or ''), None)
    evidence['recommendation_sources'] = sources
    evidence['recommendation_count'] = len(sources)
    if not sources:
        evidence['affected_items'] = []
        evidence['affected_preview'] = []
    case.evidence_json = evidence
    if sources and grouping_mode != 'finding':
        _refresh_grouped_case(case, grouping_mode=grouping_mode, now=now)


def _refresh_grouped_case(case: AlertCase, *, grouping_mode: str, now: datetime) -> None:
    evidence = dict(case.evidence_json or {})
    raw_sources = evidence.get('recommendation_sources')
    if not isinstance(raw_sources, dict) or not raw_sources:
        return
    sources = {str(key): value for key, value in raw_sources.items()}
    rule = catalog_rule(str(case.rule_key or '')) or {}
    rule_title = str(rule.get('title') or case.rule_key or 'Recommendation Alert').strip()
    targets = [
        str(source.get('target') or '').strip()
        for source in sources.values()
        if isinstance(source, dict) and str(source.get('target') or '').strip()
    ]
    severities = [_severity(source.get('severity')) for source in sources.values() if isinstance(source, dict)]
    next_severity = max(severities or [case.severity or 'info'], key=_severity_rank)
    _apply_case_severity(case, next_severity, now=now)
    count = len(sources)
    case.source_ref = str(case.rule_key or '') or case.source_ref
    case.alert_name = rule_title[:255]
    case.summary = (
        f'{count} active recommendation finding{"s" if count != 1 else ""} match {rule_title} on {case.asset_name}.'
    )
    case.target = f'{count} affected resource{"s" if count != 1 else ""}'
    if grouping_mode == 'rule_asset':
        case.namespace = None
    evidence.update(
        {
            'summary': case.summary,
            'recommendation_key': case.source_ref,
            'recommendation_count': count,
            'grouping_mode': grouping_mode,
            'affected_items': targets,
            'affected_preview': targets[:5],
        }
    )
    case.evidence_json = evidence


def _source_evidence_posture_for_finding(finding: dict[str, Any]) -> tuple[bool, str]:
    evidence = _finding_evidence(finding)
    asset_key = str(
        evidence.get('asset_key') or evidence.get('cluster_id') or evidence.get('object_storage_system_id') or ''
    ).strip()
    return _source_evidence_posture(
        domain=str(finding.get('domain') or ''),
        asset_key=asset_key,
        signal_source=str(finding.get('signal_source') or ''),
        alert_signal_profile=str(finding.get('alert_signal_profile') or ''),
    )


def _source_evidence_posture_for_state(state: RecommendationAlertState) -> tuple[bool, str]:
    rule = catalog_rule(state.rule_key) or {}
    return _source_evidence_posture(
        domain=state.domain,
        asset_key=state.asset_key,
        signal_source=str(rule.get('signal_source') or ''),
        alert_signal_profile=str(rule.get('alert_signal_profile') or ''),
    )


def _source_evidence_posture(
    *,
    domain: str,
    asset_key: str,
    signal_source: str,
    alert_signal_profile: str = '',
) -> tuple[bool, str]:
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
        if str(asset.status or '').lower() != 'connected':
            return False, 'source_unavailable'
        fast_posture = alert_signal_source_posture(
            domain=normalized_domain,
            asset_key=normalized_asset,
            profile=alert_signal_profile,
        )
        return fast_posture if fast_posture is not None else (True, '')
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

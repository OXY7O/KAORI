from __future__ import annotations

from typing import Any

from app.definitions.loader import DefinitionError
from app.extensions.db import db
from app.intelligence.catalog import INTELLIGENCE_CATALOG
from app.intelligence.rule_exceptions import (
    active_exception_counts,
    active_rule_exceptions,
    matching_rule_exception,
)
from app.models.alert_ops import AlertCase, RecommendationAlertPolicy, RecommendationAlertState, RuleException

_DEFAULT_STABILITY_MINUTES = 10
_DEFAULT_MINIMUM_OCCURRENCES = 2
_VALID_MODES = {'manual', 'automatic'}
_VALID_GROUPING_MODES = {'finding', 'rule_asset_scope', 'rule_asset'}


def base_rule_key(finding_key: str) -> str:
    return str(finding_key or '').split(':', 1)[0].strip()


def catalog_rule(rule_key: str) -> dict[str, Any] | None:
    normalized = str(rule_key or '').strip()
    if not normalized:
        return None
    for raw in INTELLIGENCE_CATALOG:
        if str(raw.get('rule_key') or '').strip() == normalized:
            return dict(raw)
    return None


def effective_alert_policy(
    rule_key: str,
    *,
    override: RecommendationAlertPolicy | None = None,
    observed_severity: str | None = None,
) -> dict[str, Any]:
    rule = catalog_rule(rule_key)
    if rule is None:
        return _disabled_policy(rule_key)
    default = _definition_policy(rule)
    row = override
    if row is None:
        row = RecommendationAlertPolicy.query.filter_by(rule_key=rule_key).first()
    if row is None:
        return _apply_observed_severity({**default, 'source': 'definition'}, observed_severity)
    policy = {
        'rule_key': rule_key,
        'eligible': bool(row.eligible),
        'mode': str(row.mode),
        'stability_window_minutes': int(row.stability_window_minutes),
        'minimum_occurrences': int(row.minimum_occurrences),
        'grouping_mode': str(row.grouping_mode),
        'source': 'override',
        'minimum_severity': default['minimum_severity'],
        'critical_stability_window_minutes': default['critical_stability_window_minutes'],
        'critical_minimum_occurrences': default['critical_minimum_occurrences'],
        'policy_id': row.id,
    }
    return _apply_observed_severity(policy, observed_severity)


def matches_alert_handling(item: dict[str, Any], selected: str | None, *, page_mode: str) -> bool:
    if page_mode != 'recommendations':
        return True
    normalized = str(selected or '').strip().lower()
    if not normalized:
        return True
    raw_handling = item.get('alert_handling')
    handling: dict[str, Any] = (
        {str(key): value for key, value in raw_handling.items()} if isinstance(raw_handling, dict) else {}
    )
    status = str(handling.get('status') or '')
    mode = str(handling.get('mode') or '')
    if normalized == 'manual_eligible':
        return status == 'eligible' and mode == 'manual'
    if normalized == 'automatic_eligible':
        return status == 'eligible' and mode == 'automatic'
    if normalized == 'recommendation_only':
        return status == 'not_eligible'
    if normalized == 'accepted_risk':
        return status == 'exception_active'
    return status == normalized


def decorate_recommendation_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not findings:
        return findings
    rule_keys = {base_rule_key(str(item.get('rule_key') or '')) for item in findings}
    overrides = {
        row.rule_key: row
        for row in RecommendationAlertPolicy.query.filter(RecommendationAlertPolicy.rule_key.in_(rule_keys)).all()
    }
    finding_keys = [str(item.get('rule_key') or '') for item in findings]
    states = {
        row.finding_key: row
        for row in RecommendationAlertState.query.filter(RecommendationAlertState.finding_key.in_(finding_keys)).all()
    }
    case_ids = {row.alert_case_id for row in states.values() if row.alert_case_id is not None}
    cases = {row.id: row for row in AlertCase.query.filter(AlertCase.id.in_(case_ids)).all()} if case_ids else {}
    exceptions = active_rule_exceptions(rule_keys)
    for item in findings:
        finding_key = str(item.get('rule_key') or '')
        rule_key = base_rule_key(finding_key)
        policy = effective_alert_policy(
            rule_key,
            override=overrides.get(rule_key),
            observed_severity=str(item.get('severity') or 'info'),
        )
        state = states.get(finding_key)
        case = cases.get(state.alert_case_id) if state and state.alert_case_id else None
        exception = matching_rule_exception(item, rows=exceptions)
        item['base_rule_key'] = rule_key
        item['alert_handling'] = _handling_view(policy, state=state, case=case, exception=exception)
    return findings


def decorate_catalog_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rules:
        return rules
    keys = {str(rule.get('rule_key') or '') for rule in rules}
    overrides = {
        row.rule_key: row
        for row in RecommendationAlertPolicy.query.filter(RecommendationAlertPolicy.rule_key.in_(keys)).all()
    }
    exception_counts = active_exception_counts(keys)
    for rule in rules:
        key = str(rule.get('rule_key') or '')
        rule['alert_escalation'] = effective_alert_policy(key, override=overrides.get(key))
        rule['active_exception_count'] = int(exception_counts.get(key, 0))
    return rules


def upsert_recommendation_alert_policy(
    *,
    rule_key: str,
    eligible: bool,
    mode: str,
    stability_window_minutes: int,
    minimum_occurrences: int,
    grouping_mode: str,
    actor_user_id: int | None,
) -> RecommendationAlertPolicy:
    rule = catalog_rule(rule_key)
    if rule is None:
        raise ValueError('The selected Intelligence rule does not exist.')
    if str(rule.get('status') or '') != 'available':
        raise ValueError('Only available KAORI recommendation rules can be promoted into Alert Operations.')
    normalized_mode = str(mode or '').strip().lower()
    if normalized_mode not in _VALID_MODES:
        raise ValueError('Escalation mode must be Manual or Automatic.')
    normalized_grouping = str(grouping_mode or '').strip().lower()
    if normalized_grouping not in _VALID_GROUPING_MODES:
        raise ValueError('Select a supported Alert Operations grouping mode.')
    stability = max(0, min(int(stability_window_minutes or 0), 1440))
    occurrences = max(1, min(int(minimum_occurrences or 1), 100))
    row = RecommendationAlertPolicy.query.filter_by(rule_key=rule_key).first()
    if row is None:
        row = RecommendationAlertPolicy()
        row.rule_key = rule_key
        db.session.add(row)
    row.eligible = bool(eligible)
    row.mode = normalized_mode
    row.stability_window_minutes = stability
    row.minimum_occurrences = occurrences
    row.grouping_mode = normalized_grouping
    row.updated_by_user_id = actor_user_id
    return row


def _definition_policy(rule: dict[str, Any]) -> dict[str, Any]:
    configured = rule.get('alert_escalation')
    if not isinstance(configured, dict):
        configured = {}
    severity = str(rule.get('severity') or '').strip().lower()
    status = str(rule.get('status') or '').strip().lower()
    logic_type = str(rule.get('logic_type') or '').strip().lower()
    default_eligible = (
        status == 'available' and severity in {'warning', 'critical'} and logic_type != 'alert_enrichment'
    )
    eligible = bool(configured.get('eligible', default_eligible))
    minimum_severity = str(configured.get('minimum_severity') or 'warning').strip().lower()
    if minimum_severity not in {'info', 'warning', 'critical'}:
        raise DefinitionError(
            f'Rule {rule.get("rule_key")!r} has unsupported minimum alert severity {minimum_severity!r}.'
        )
    default_mode = 'automatic' if eligible else 'manual'
    mode = str(configured.get('mode') or default_mode).strip().lower()
    if mode not in _VALID_MODES:
        raise DefinitionError(f'Rule {rule.get("rule_key")!r} has unsupported alert escalation mode {mode!r}.')
    grouping = str(configured.get('grouping_mode') or 'finding').strip().lower()
    if grouping not in _VALID_GROUPING_MODES:
        raise DefinitionError(
            f'Rule {rule.get("rule_key")!r} has unsupported alert escalation grouping mode {grouping!r}.'
        )
    stability = max(0, min(int(configured.get('stability_window_minutes', _DEFAULT_STABILITY_MINUTES)), 1440))
    occurrences = max(1, min(int(configured.get('minimum_occurrences', _DEFAULT_MINIMUM_OCCURRENCES)), 100))
    critical_stability = max(0, min(int(configured.get('critical_stability_window_minutes', 0)), 1440))
    critical_occurrences = max(1, min(int(configured.get('critical_minimum_occurrences', 1)), 100))
    return {
        'rule_key': str(rule.get('rule_key') or ''),
        'eligible': eligible,
        'mode': mode,
        'stability_window_minutes': stability,
        'minimum_occurrences': occurrences,
        'grouping_mode': grouping,
        'minimum_severity': minimum_severity,
        'critical_stability_window_minutes': critical_stability,
        'critical_minimum_occurrences': critical_occurrences,
        'source': 'definition',
        'policy_id': None,
    }


def _apply_observed_severity(policy: dict[str, Any], observed_severity: str | None) -> dict[str, Any]:
    configured_eligible = bool(policy.get('eligible'))
    if observed_severity is None:
        return {**policy, 'configured_eligible': configured_eligible, 'severity_eligible': True}
    severity_eligible = _severity_rank(observed_severity) >= _severity_rank(
        str(policy.get('minimum_severity') or 'warning')
    )
    return {
        **policy,
        'configured_eligible': configured_eligible,
        'severity_eligible': severity_eligible,
        'eligible': configured_eligible and severity_eligible,
    }


def _severity_rank(value: str) -> int:
    return {'info': 1, 'warning': 2, 'critical': 3}.get(str(value or '').strip().lower(), 0)


def _handling_view(
    policy: dict[str, Any],
    *,
    state: RecommendationAlertState | None,
    case: AlertCase | None,
    exception: RuleException | None,
) -> dict[str, Any]:
    if exception is not None:
        status = 'exception_active'
        label = 'Accepted Risk'
        tone = 'info'
    elif case is not None and case.source_state == 'unknown' and case.workflow_state != 'closed':
        status = 'source_unknown'
        label = 'Alert · Source Unknown'
        tone = 'warning'
    elif case is not None and case.source_state == 'resolved' and case.workflow_state != 'closed':
        status = 'resolved_pending'
        label = 'Resolved · Verify'
        tone = 'warning'
    elif case is not None and case.workflow_state != 'closed':
        status = 'escalated'
        label = 'Alert Open'
        tone = 'warning' if case.severity != 'critical' else 'critical'
    elif case is not None and case.closure_reason == 'manual_withdrawal':
        status = 'withdrawn'
        label = 'Alert Withdrawn'
        tone = 'unknown'
    elif case is not None and case.closure_reason == 'source_decommissioned':
        status = 'retired'
        label = 'Source Decommissioned'
        tone = 'unknown'
    elif case is not None and case.workflow_state == 'closed':
        status = 'resolved'
        label = 'Resolved Alert'
        tone = 'normal'
    elif policy['eligible']:
        status = 'eligible'
        label = 'Auto Eligible' if policy['mode'] == 'automatic' else 'Manual Eligible'
        tone = 'info'
    else:
        status = 'not_eligible'
        label = 'Recommendation Only'
        tone = 'unknown'
    return {
        **policy,
        'status': status,
        'label': label,
        'tone': tone,
        'case_public_id': case.public_id if case is not None else None,
        'case_workflow_state': case.workflow_state if case is not None else None,
        'occurrence_count': int(state.occurrence_count) if state is not None else 0,
        'first_seen_at': state.first_seen_at if state is not None else None,
        'exception_public_id': exception.public_id if exception is not None else None,
        'exception_reference': exception.risk_reference if exception is not None else None,
        'exception_expires_at': exception.expires_at if exception is not None else None,
    }


def _disabled_policy(rule_key: str) -> dict[str, Any]:
    return {
        'rule_key': rule_key,
        'eligible': False,
        'mode': 'manual',
        'stability_window_minutes': _DEFAULT_STABILITY_MINUTES,
        'minimum_occurrences': _DEFAULT_MINIMUM_OCCURRENCES,
        'grouping_mode': 'finding',
        'minimum_severity': 'warning',
        'critical_stability_window_minutes': 0,
        'critical_minimum_occurrences': 1,
        'configured_eligible': False,
        'severity_eligible': False,
        'source': 'missing',
        'policy_id': None,
    }

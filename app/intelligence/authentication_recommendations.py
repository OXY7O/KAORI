"""Reserved native authentication recommendation source contract (#5423).

The committed signal is domain evidence, not an admitted AlertCase. Keep
the rule reserved until hosted qualification and explicit security approval.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from flask import has_request_context
from flask_login import current_user

from app.intelligence.alert_signals.authentication import (
    ASSET_KEY,
    BUDGET_THRESHOLD,
    MAX_ROWS,
    RECOVERY_THRESHOLD,
    REJECTION_THRESHOLD,
    SOURCE_THRESHOLD,
    TARGET_THRESHOLD,
    WINDOW_MINUTES,
    closed_window,
    read_authentication_abuse_signal,
)

RULE_KEY = 'authentication.security.login_abuse_review'
FINDING_KEY = f'{RULE_KEY}:deployment'
_COUNT_KEYS = (
    'sample_rows',
    'credential_rejections',
    'known_targets',
    'distinct_observed_sources',
    'peak_known_target_rejections',
    'peak_current_recovery_principal_rejections',
    'endpoint_rate_limited',
    'challenge_rejections',
    'identity_budget_observations',
    'enforced_lock_transitions',
    'monitor_threshold_observations',
)
_EVENT_COUNT_KEYS = (
    'credential_rejections', 'endpoint_rate_limited', 'challenge_rejections',
    'identity_budget_observations', 'enforced_lock_transitions', 'monitor_threshold_observations',
)


def _can_view_authentication_evidence() -> bool:
    """Use the current protected local recovery principal; deny worker reads."""
    return bool(
        has_request_context()
        and current_user.is_authenticated
        and current_user.is_active
        and current_user.auth_source == 'database'
        and current_user.is_super_admin
        and current_user.has_permission('intelligence.view')
    )


def _indicators(counts: dict[str, int]) -> list[str]:
    indicators: list[str] = []
    if counts['credential_rejections'] >= REJECTION_THRESHOLD:
        indicators.append('elevated_credential_rejections')
        if counts['known_targets'] >= TARGET_THRESHOLD:
            indicators.append('multi_target_rejection_pattern')
        if counts['distinct_observed_sources'] >= SOURCE_THRESHOLD:
            indicators.append('multi_source_rejection_pattern')
    if counts['peak_current_recovery_principal_rejections'] >= RECOVERY_THRESHOLD:
        indicators.append('recovery_principal_rejection_pattern')
    if counts['identity_budget_observations'] >= BUDGET_THRESHOLD:
        indicators.append('shared_budget_pressure')
    if counts['enforced_lock_transitions']:
        indicators.append('enforced_lock_transition')
    return indicators


def qualified_abuse_evidence(snapshot: dict[str, Any], *, now: datetime) -> dict[str, Any] | None:
    """Allowlist and cross-check a complete, current committed aggregate.

    Partial/missing/stale/disabled/malformed evidence is not a quiet window.
    Even a qualified zero is bounded audit observation, not verified recovery.
    """
    if snapshot.get('state') != 'fresh':
        return None
    payload = snapshot.get('payload')
    if not isinstance(payload, dict):
        return None
    if (
        type(payload.get('schema_version')) is not int or payload['schema_version'] != 1
        or payload.get('coverage') != 'bounded_window'
        or payload.get('source_authority') != 'committed_activity_audit'
        or payload.get('missed_prior_window') is not False
    ):
        return None
    counts: dict[str, int] = {}
    for key in _COUNT_KEYS:
        value = payload.get(key)
        if type(value) is not int or not 0 <= value <= MAX_ROWS:
            return None
        counts[key] = value
    rejection_count = counts['credential_rejections']
    if (
        sum(counts[key] for key in _EVENT_COUNT_KEYS) > counts['sample_rows']
        or any(counts[key] > rejection_count for key in (
            'known_targets', 'distinct_observed_sources', 'peak_known_target_rejections',
        ))
        or counts['peak_current_recovery_principal_rejections'] > counts['peak_known_target_rejections']
        or (counts['known_targets'] == 0) != (counts['peak_known_target_rejections'] == 0)
    ):
        return None
    try:
        start = datetime.fromisoformat(str(payload.get('window_start')))
        end = datetime.fromisoformat(str(payload.get('window_end')))
    except ValueError:
        return None
    if (
        start.tzinfo is None or end.tzinfo is None
        or start.utcoffset() != timedelta(0) or end.utcoffset() != timedelta(0)
        or end - start != timedelta(minutes=WINDOW_MINUTES)
        or end.second != 0 or end.microsecond != 0 or end.minute % WINDOW_MINUTES != 0
        or (start, end) != closed_window(now)
    ):
        return None
    indicators = _indicators(counts)
    observed_indicators = payload.get('indicators')
    if not isinstance(observed_indicators, list) or observed_indicators != indicators:
        return None
    return {
        **counts,
        'asset_key': ASSET_KEY,
        'source_status': 'ready',
        'source_coverage': 'Bounded committed authentication audit window',
        'window_start': start.isoformat(),
        'window_end': end.isoformat(),
        'indicators': indicators,
        'attack_confirmed': False,
    }


def build_authentication_recommendation_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Central evaluator entry; no active finding while the definition is reserved."""
    rule = rules.get(RULE_KEY)
    if rule is None or rule.get('status') != 'available' or not _can_view_authentication_evidence():
        return []
    evidence = qualified_abuse_evidence(read_authentication_abuse_signal(), now=datetime.now(UTC))
    if evidence is None or not evidence['indicators']:
        return []
    return [{
        **rule,
        'rule_key': FINDING_KEY,
        'affected_summary': 'KAORI authentication deployment',
        'summary': 'Qualified bounded authentication observations contain indicators requiring investigation.',
        'condition_summary': 'One or more recognized aggregate abuse indicators were observed; attack not confirmed.',
        'evidence': evidence,
    }]

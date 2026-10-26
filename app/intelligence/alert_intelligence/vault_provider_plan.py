"""Read-only HV-12 candidate plan for source-qualified Vault provider AlertCases.

This module deliberately performs no case writes or provider calls. The source
observation is a short-lived, exact-binding committed AlertSignalSnapshot.
Missing alerts, unobserved samples and failed snapshots NEVER prove recovery.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.intelligence.alert_signals.vault_source import (
    _utc,
    _validated_binding,
    read_vault_alert_observations,
)
from app.models.alert_ops import AlertCase

_CASE_PREFIX = 'vault-alert:'
_PROFILE = 'vault-alert-hmac-v1'
_MAX_CASES = 100
_CASE_KEY_RE = re.compile(r'vault-alert:[0-9a-f]{64}\Z')
_SAFE_PROVENANCE_KEYS = frozenset({
    'correlation_profile', 'source_binding_id', 'source_integration_id',
})
_ACTIONS = frozenset({
    'create_candidate',
    'refresh_candidate',
    'retain_unverified',
    'review_source',
    'review_closed_case',
})


def _result(status: str, *, candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = candidates if status == 'qualified' and candidates is not None else None
    return {
        'status': status,
        'candidates': rows,
        'candidate_count': len(rows) if rows is not None else None,
        'basis': 'Committed, exact-source observations; candidate actions only, never case transitions',
    }


def _provenance_matches(case: AlertCase, *, source_id: int, binding_id: int) -> bool:
    evidence = case.evidence_json
    return bool(
        case.source_type == 'provider_alert'
        and case.domain == 'secrets_pki'
        and case.asset_type == 'vault_instance'
        and case.source_ref == case.case_key
        and _CASE_KEY_RE.fullmatch(case.case_key) is not None
        and case.routing_state == 'suppressed'
        and case.routing_override_reason == 'policy_ineligible'
        and isinstance(case.labels_json, dict)
        and not case.labels_json
        and isinstance(evidence, dict)
        and set(evidence) == _SAFE_PROVENANCE_KEYS
        and evidence.get('correlation_profile') == _PROFILE
        and type(evidence.get('source_binding_id')) is int
        and evidence['source_binding_id'] == binding_id
        and type(evidence.get('source_integration_id')) is int
        and evidence['source_integration_id'] == source_id
    )


def build_vault_provider_case_plan(
    *,
    binding_id: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return internal candidates only; do not infer resolved from absence.

    Existing provider-origin cases are never modified here. Future activation
    requires resource-scoped RBAC, routing-policy admission and tested source
    lifecycle semantics under a separately authorized child issue.
    """
    instant = _utc(now or datetime.now(UTC))
    if instant is None:
        return _result('unavailable')
    eligible = _validated_binding(binding_id, now=instant)
    if eligible is None:
        return _result('unavailable')
    binding, source = eligible
    observation = read_vault_alert_observations(binding_id=binding.id, now=instant)
    state = observation['state']
    if state != 'fresh':
        return _result('unobserved' if state == 'unobserved' else 'unavailable')
    entries = observation['entries']
    if not isinstance(entries, list) or not 1 <= len(entries) <= _MAX_CASES:
        return _result('blocked')
    proposed_keys = {_CASE_PREFIX + entry['handle'] for entry in entries}
    if len(proposed_keys) != len(entries):
        return _result('blocked')
    # The internal plan must detect historical replays and ambiguous active
    # records; it does not reopen a previously closed occurrence.
    existing = (
        AlertCase.query.filter(
            AlertCase.domain == 'secrets_pki',
            AlertCase.asset_key == binding.asset_key,
            AlertCase.case_key.like(_CASE_PREFIX + '%'),
        )
        .order_by(AlertCase.id.desc())
        .limit(_MAX_CASES + 1)
        .all()
    )
    if len(existing) > _MAX_CASES:
        return _result('blocked')
    cases: dict[str, AlertCase] = {}
    for case in existing:
        if not _provenance_matches(case, source_id=source.id, binding_id=binding.id):
            return _result('blocked')
        if case.case_key in cases:
            return _result('blocked')
        cases[case.case_key] = case

    # Key collision with another domain/asset/source must never silently
    # attach or materialize a foreign provider AlertCase.
    collisions = (
        AlertCase.query.filter(AlertCase.case_key.in_(proposed_keys))
        .limit(_MAX_CASES + 1)
        .all()
    )
    if len(collisions) > _MAX_CASES:
        return _result('blocked')
    for case in collisions:
        if cases.get(case.case_key) is not case:
            return _result('blocked')

    plan: list[dict[str, Any]] = []
    for entry in entries:
        case_key = _CASE_PREFIX + entry['handle']
        prior = cases.get(case_key)
        if prior is not None and prior.workflow_state == 'closed':
            action = 'review_closed_case'
        elif entry['source_state'] != 'firing':
            action = 'retain_unverified' if prior is not None else 'review_source'
        elif prior is None:
            action = 'create_candidate'
        elif prior.source_state == 'firing':
            action = 'refresh_candidate'
        else:
            action = 'retain_unverified'
        plan.append({
            'action': action,
            'case_key': case_key,
            'severity': entry['severity'],
            'observed_source_state': entry['source_state'],
            'existing_case_id': prior.id if prior is not None else None,
            'proposed_routing_state': 'suppressed',
        })

    # A fully fresh but non-exhaustive Alertmanager response cannot prove
    # resolution, including absence of a previously committed case key.
    for case_key, case in cases.items():
        if case_key not in proposed_keys and case.workflow_state != 'closed':
            plan.append({
                'action': 'retain_unverified',
                'case_key': case_key,
                'severity': case.severity,
                'observed_source_state': 'unknown',
                'existing_case_id': case.id,
                'proposed_routing_state': 'suppressed',
            })
    if any(item['action'] not in _ACTIONS for item in plan):
        return _result('blocked')
    plan.sort(key=lambda row: row['case_key'])
    return _result('qualified', candidates=plan)

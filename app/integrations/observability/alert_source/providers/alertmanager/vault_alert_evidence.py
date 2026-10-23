"""Fail-closed, allowlisted Vault alert source evidence at binding validation.

This summary describes the bounded Alertmanager result observed during an
explicit binding validation; it is not a live stream, AlertCase, or recovery
signal. Raw alert names, labels, annotations, paths and fingerprints are never
returned or committed.
"""

from __future__ import annotations

from typing import Any

_MAX_ALERT_ROWS = 100
_ALLOWED_STATES = frozenset({'active', 'suppressed', 'unprocessed'})
_ALLOWED_SEVERITIES = frozenset({'critical', 'warning', 'info'})
_COUNT_FIELDS = (
    'observed_rows', 'firing', 'suppressed', 'unprocessed',
    'critical', 'warning', 'info',
)


def _result(status: str, counts: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        'status': status,
        'identity_observed': status == 'qualified',
        **{name: counts.get(name) if counts is not None else None for name in _COUNT_FIELDS},
        'basis': 'Alertmanager matching rows at binding validation; not current AlertCases or recovery',
    }


def qualify_vault_alert_sample(*, asset_key: str, payload: object) -> dict[str, Any]:
    """Qualify bounded raw Alertmanager rows using exact canonical identity.

    All-or-nothing: do not make partial/stale/malformed rows look like clean
    observations. This pure transform performs no provider calls or writes.
    """
    if (
        not isinstance(asset_key, str)
        or not asset_key.isascii()
        or not asset_key.isdecimal()
        or not 1 <= len(asset_key) <= 10
        or int(asset_key) < 1
        or str(int(asset_key)) != asset_key
    ):
        return _result('blocked')
    if not isinstance(payload, list) or len(payload) > _MAX_ALERT_ROWS:
        return _result('blocked')
    if not payload:
        return _result('unobserved')

    counts = {field: 0 for field in _COUNT_FIELDS}
    for alert in payload:
        if not isinstance(alert, dict):
            return _result('blocked')
        labels = alert.get('labels')
        if not isinstance(labels, dict) or labels.get('vault_instance') != asset_key:
            return _result('blocked')
        status = alert.get('status')
        state = status.get('state') if isinstance(status, dict) else None
        severity = labels.get('severity')
        if not isinstance(state, str) or state not in _ALLOWED_STATES:
            return _result('incomplete')
        if not isinstance(severity, str) or severity not in _ALLOWED_SEVERITIES:
            return _result('incomplete')
        counts['observed_rows'] += 1
        counts['firing' if state == 'active' else state] += 1
        counts[severity] += 1
    return _result('qualified', counts)

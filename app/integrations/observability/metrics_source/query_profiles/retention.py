from __future__ import annotations

from collections.abc import Sequence
from typing import Any

_DEFAULT_RETENTION_HORIZONS = ('24h', '7d', '30d', '60d')


def retention_horizons(definitions: Sequence[Any]) -> tuple[str, ...]:
    horizons = set(_DEFAULT_RETENTION_HORIZONS)
    horizons.update(
        definition.required_history for definition in definitions if getattr(definition, 'required_history', None)
    )
    return tuple(sorted(horizons, key=horizon_seconds))


def maximum_history(horizons: set[str]) -> str | None:
    return max(horizons, key=horizon_seconds) if horizons else None


def horizon_seconds(value: str) -> int:
    text = str(value).strip().lower()
    amount = int(text[:-1])
    unit = text[-1]
    multipliers = {'m': 60, 'h': 3_600, 'd': 86_400}
    if unit not in multipliers:
        raise ValueError(f'Unsupported history horizon: {value}')
    return amount * multipliers[unit]


def technical_history_check(
    horizon: str,
    retention: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    evidence = (retention or {}).get(horizon) or {}
    available = bool(evidence.get('available'))
    message = str(evidence.get('message') or f'The required {horizon} retention probe was not recorded.')
    return {
        'key': f'history.{horizon}',
        'label': f'{horizon} History Availability',
        'status': 'ready' if available else 'failed',
        'status_label': 'Ready' if available else 'Failed',
        'evidence': message,
        'query': 'count(up)',
        'registered_query': 'count(up)',
        'identity_keys': [],
        'matching_identity_count': 0,
        'series_count_display': '',
        'value_summary': str(evidence.get('sample_time') or ''),
        'error_detail': '',
    }


def long_term_history_assessment(
    retention: dict[str, dict[str, Any]],
    *,
    horizon: str = '90d',
) -> dict[str, Any]:
    check = technical_history_check(horizon, retention)
    ready = check['status'] == 'ready'
    message = str(check['evidence'])
    return {
        'status': 'available' if ready else 'missing',
        'evidence': message,
        'observed': message,
        'expected': (
            f'Historical samples must be queryable at the {horizon} horizon because the canonical '
            'Kubernetes Forecast query contract requires 90 days of source history.'
        ),
        'technical_checks': [check],
        'possible_causes': [
            f'The selected endpoint does not retain {horizon} of queryable samples.',
            'Thanos Query is reachable but its upstream Store/Sidecar history does not cover the required horizon.',
            'The binding targets a recent-only Prometheus source instead of the historical Metrics Source.',
        ],
    }


def history_remediation(horizon: str) -> str:
    return (
        f'Use a Metrics Source that exposes at least {horizon} of queryable history for this consumer contract. '
        'For Thanos, verify Query/Store/Sidecar history coverage and the selected cluster identity, then rerun '
        'Binding Validation.'
    )

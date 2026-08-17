from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import current_app, has_app_context

DEFAULT_RECENT_WINDOW_HOURS = 24
ROUTING_HORIZONS = frozenset({'recent', 'historical', 'balanced'})


def normalize_routing_policy(value: dict[str, Any] | None) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    horizon = str(payload.get('query_horizon') or 'balanced').strip().lower()
    if horizon not in ROUTING_HORIZONS:
        horizon = 'balanced'
    try:
        weight = min(max(int(payload.get('weight', 100)), 1), 100)
    except (TypeError, ValueError):
        weight = 100
    return {'query_horizon': horizon, 'weight': weight}


def recent_window_hours() -> int:
    if not has_app_context():
        return DEFAULT_RECENT_WINDOW_HOURS
    try:
        configured = current_app.config.get('METRICS_RECENT_WINDOW_HOURS', DEFAULT_RECENT_WINDOW_HOURS)
        return min(max(int(configured), 1), 8760)
    except (TypeError, ValueError):
        return DEFAULT_RECENT_WINDOW_HOURS


def query_horizon_for_timestamp(value: object) -> str:
    timestamp = _parse_timestamp(value)
    if timestamp is None:
        return 'recent'
    cutoff = datetime.now(UTC).timestamp() - (recent_window_hours() * 3600)
    return 'historical' if timestamp < cutoff else 'recent'


def query_horizon_for_range(start: object, end: object) -> str:
    start_timestamp = _parse_timestamp(start)
    if start_timestamp is None:
        return 'recent'
    cutoff = datetime.now(UTC).timestamp() - (recent_window_hours() * 3600)
    return 'historical' if start_timestamp < cutoff else 'recent'


def routing_rank(policy: dict[str, Any] | None, *, requested_horizon: str) -> tuple[int, int]:
    normalized = normalize_routing_policy(policy)
    preference = normalized['query_horizon']
    requested = requested_horizon if requested_horizon in {'recent', 'historical'} else 'balanced'
    if requested == 'balanced' or preference == requested:
        horizon_rank = 0
    elif preference == 'balanced':
        horizon_rank = 1
    else:
        horizon_rank = 2
    return horizon_rank, -int(normalized['weight'])


def _parse_timestamp(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        normalized = text[:-1] + '+00:00' if text.endswith('Z') else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()

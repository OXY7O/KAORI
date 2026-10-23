"""Safe freshness qualification for committed public Vault PKI collection states."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

_FRESHNESS = timedelta(hours=24)


def _utc(value: datetime | None) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)


def qualified_committed_pki_count(
    state: Any,
    *,
    instant: datetime,
    count_field: str,
    max_count: int,
) -> int | None:
    """Verify a ready, bounded and coherently committed source observation.

    Caller must separately verify exact source/mount coverage and
    integration readiness. No provider calls or Secret references.
    """
    now = _utc(instant)
    observed = _utc(getattr(state, 'last_observed_at', None))
    committed = _utc(getattr(state, 'last_committed_at', None))
    count = getattr(state, count_field, None)
    if (
        now is None or observed is None or committed is None
        or getattr(state, 'status', None) != 'ready'
        or type(count) is not int or not 0 <= count <= max_count
        or not observed <= committed <= now
        or now - observed > _FRESHNESS
        or now - committed > _FRESHNESS
    ):
        return None
    return count

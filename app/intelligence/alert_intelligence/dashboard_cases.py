from __future__ import annotations

from collections.abc import Iterable

from app.models.alert_ops import AlertCase


def active_recommendation_alert_cases(
    *,
    domain: str,
    asset_key: str,
) -> list[AlertCase]:
    """Return open KAORI Alert Intelligence cases for one managed asset.

    Dashboard surfaces intentionally consume the current Alert Intelligence
    contract: recommendation-origin durable AlertCase records. Raw provider
    alert snapshots remain owned by Analytics and freshness/readiness views.
    """

    normalized_asset = str(asset_key or '').strip()
    if not normalized_asset:
        return []
    return (
        AlertCase.query.filter(
            AlertCase.domain == str(domain),
            AlertCase.asset_key == normalized_asset,
            AlertCase.source_type == 'recommendation',
            AlertCase.source_state.in_(('firing', 'unknown')),
            AlertCase.workflow_state != 'closed',
        )
        .order_by(AlertCase.first_seen_at.desc(), AlertCase.id.desc())
        .all()
    )


def active_recommendation_alert_cases_by_asset(
    *,
    domain: str,
    asset_keys: Iterable[str],
) -> dict[str, list[AlertCase]]:
    """Load active Alert Intelligence cases for multiple assets in one query."""

    normalized_keys = {str(value or '').strip() for value in asset_keys if str(value or '').strip()}
    if not normalized_keys:
        return {}
    rows = (
        AlertCase.query.filter(
            AlertCase.domain == str(domain),
            AlertCase.asset_key.in_(normalized_keys),
            AlertCase.source_type == 'recommendation',
            AlertCase.source_state.in_(('firing', 'unknown')),
            AlertCase.workflow_state != 'closed',
        )
        .order_by(AlertCase.first_seen_at.desc(), AlertCase.id.desc())
        .all()
    )
    grouped: dict[str, list[AlertCase]] = {key: [] for key in normalized_keys}
    for case in rows:
        grouped.setdefault(str(case.asset_key), []).append(case)
    return grouped

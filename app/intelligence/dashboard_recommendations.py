from __future__ import annotations

from typing import Any

from app.intelligence.service import get_active_recommendation_findings

MAX_DASHBOARD_RECOMMENDATIONS = 5


def get_dashboard_recommendation_findings(
    *,
    domain: str,
    asset_key: str | None,
    limit: int = MAX_DASHBOARD_RECOMMENDATIONS,
) -> list[dict[str, Any]]:
    """Return central Intelligence findings for compact Dashboard consumption.

    Intelligence owns ranking and finding semantics. Dashboards only apply the
    product-wide maximum-card boundary and an explicit domain/asset scope.
    """

    normalized_asset = str(asset_key or '').strip() or None
    bounded_limit = min(max(int(limit), 0), MAX_DASHBOARD_RECOMMENDATIONS)
    return get_active_recommendation_findings(
        domain=domain,
        asset_key=normalized_asset,
        limit=bounded_limit,
    )

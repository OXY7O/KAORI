from __future__ import annotations

from typing import Any

from app.dashboards.kubernetes.schema import ForecastItem, ForecastSnapshot
from app.dashboards.kubernetes.utils import forecast_insight


def build_forecast_snapshot(*, context: dict[str, Any] | None, unavailable_reason: str) -> ForecastSnapshot:
    if not context:
        return ForecastSnapshot(
            items=default_forecast_items('Unknown', 'Worker snapshot unavailable'),
            insight=unavailable_reason,
            source_status='Unavailable',
        )

    payload = context.get('forecast_payload') or {}
    if not isinstance(payload, dict):
        return ForecastSnapshot(
            items=default_forecast_items('Unknown', 'Invalid snapshot'),
            insight='Committed forecast snapshot has an invalid payload.',
            source_status='Unavailable',
        )

    horizon_days = int(payload.get('horizon_days') or 90)
    raw_items = payload.get('items', [])
    items: list[ForecastItem] = []
    if isinstance(raw_items, list):
        for item in raw_items[:4]:
            if not isinstance(item, dict):
                continue
            status = str(item.get('status_label') or item.get('status') or 'Unknown').title()
            projected = item.get('projected_percent')
            projection = (
                f'Projected {float(projected):.0f}% in {horizon_days} days'
                if isinstance(projected, int | float)
                else 'Projection unavailable'
            )
            items.append(
                ForecastItem(
                    label=str(item.get('label') or 'Resource'),
                    risk=status,
                    projection=projection,
                    icon=str(item.get('icon') or 'activity'),
                    projected_percent=float(projected) if isinstance(projected, int | float) else None,
                )
            )

    has_data = bool(payload.get('has_data')) and bool(items)
    return ForecastSnapshot(
        items=items or default_forecast_items('Unknown', 'Insufficient data'),
        insight=(
            forecast_insight(payload)
            if has_data
            else str(payload.get('message') or 'Insufficient trend data for reliable forecasting.')
        ),
        source_status='Available' if has_data else 'Unavailable',
        horizon_days=horizon_days,
    )


def default_forecast_items(risk: str, projection: str) -> list[ForecastItem]:
    return [
        ForecastItem(label='CPU Growth', risk=risk, projection=projection, icon='cpu'),
        ForecastItem(label='Memory Growth', risk=risk, projection=projection, icon='memory-stick'),
        ForecastItem(label='Storage Growth', risk=risk, projection=projection, icon='hard-drive'),
        ForecastItem(label='Pod Growth', risk=risk, projection=projection, icon='container'),
    ]

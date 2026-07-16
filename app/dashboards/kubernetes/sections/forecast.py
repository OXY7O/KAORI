from __future__ import annotations

from typing import Any

from app.dashboards.kubernetes.schema import ForecastItem, ForecastSnapshot
from app.dashboards.kubernetes.utils import forecast_insight


def build_forecast_snapshot(*, live_cluster: Any | None) -> ForecastSnapshot:
    if live_cluster is None:
        return ForecastSnapshot(
            items=default_forecast_items('Unknown', 'Select a cluster'),
            insight='Select a specific cluster to load compact forecast and growth risk snapshots.',
            source_status='Unavailable',
        )

    try:
        from app.analytics.forecast.service import ForecastAnalysisService
        from app.analytics.utilization.service import UtilizationService
        from app.prometheus.service import PrometheusService

        utilization = UtilizationService(PrometheusService(live_cluster))
        service = ForecastAnalysisService(utilization_service=utilization, cluster=live_cluster)
        payload = service.get_forecast_analysis(
            namespace='',
            history_window='30d',
            forecast_horizon='30d',
            resource='all',
        )
    except Exception as exc:
        return ForecastSnapshot(
            items=default_forecast_items('Unknown', 'Forecast unavailable'),
            insight=f'Forecast snapshot unavailable: {exc}',
            source_status='Unavailable',
        )

    raw_items = payload.get('items', [])
    items: list[ForecastItem] = []
    if isinstance(raw_items, list):
        for item in raw_items[:4]:
            status = str(item.get('status_label') or item.get('status') or 'Unknown').title()
            projected = item.get('projected_percent')
            projection = (
                f'Projected {float(projected):.0f}% in 30 days'
                if isinstance(projected, int | float)
                else 'Projection unavailable'
            )
            items.append(
                ForecastItem(
                    label=str(item.get('label') or 'Resource'),
                    risk=status,
                    projection=projection,
                    icon=str(item.get('icon') or 'activity'),
                )
            )

    has_data = bool(payload.get('has_data')) and bool(items)
    return ForecastSnapshot(
        items=items or default_forecast_items('Unknown', 'Insufficient data'),
        insight=forecast_insight(payload)
        if has_data
        else str(payload.get('message') or 'Insufficient trend data for reliable forecasting.'),
        source_status='Available' if has_data else 'Unavailable',
    )


def default_forecast_items(risk: str, projection: str) -> list[ForecastItem]:
    return [
        ForecastItem(label='CPU Growth', risk=risk, projection=projection, icon='cpu'),
        ForecastItem(label='Memory Growth', risk=risk, projection=projection, icon='memory-stick'),
        ForecastItem(label='Storage Growth', risk=risk, projection=projection, icon='hard-drive'),
        ForecastItem(label='Pod Growth', risk=risk, projection=projection, icon='container'),
    ]

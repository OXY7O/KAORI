from __future__ import annotations

from typing import Any

from app.analytics.overview.service import get_analytics_overview
from app.models.report import Report

def get_report_analytics_overview_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        selected_cluster_id = report.cluster_id or None
        time_range = report.period or '24h'

        return get_analytics_overview(
            selected_cluster_id=selected_cluster_id,
            time_range=time_range,
        )
    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }

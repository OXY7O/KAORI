from __future__ import annotations

from typing import Any

from app.reports.export.html_pdf.analytics_overview_sections import methodology_page, recommendation_page

from .context import OverviewContext, common_presentation
from .freshness import freshness_page
from .pages import (
    alerts_page,
    capacity_pressure_page,
    cover_page,
    executive_page,
    resource_posture_page,
    top_consumers_page,
    trend_forecast_page,
)
from .reporting import reporting
from .state import build_overview_state


def build_overview_presentation(context: OverviewContext) -> dict[str, Any]:
    state = build_overview_state(context)
    recommendation_content = recommendation_page(state.recommendation_items)
    methodology_content = methodology_page(
        source_rows=state.source_rows,
        inventory=state.inventory,
        period_label=context.period_label,
        data_cutoff=context.data_cutoff,
        forecast_snapshot=state.forecast_snapshot,
        snapshot_summary=state.snapshot_summary,
    )
    return {
        **common_presentation(context),
        'cover': cover_page(context, state),
        'executive': executive_page(state),
        'resource_posture': resource_posture_page(state),
        'trend_forecast': trend_forecast_page(state),
        'top_consumers': top_consumers_page(context, state),
        'capacity_pressure': capacity_pressure_page(state),
        'alerts': alerts_page(state),
        'reporting': reporting(state.reporting_summary),
        'inventory': state.inventory,
        'freshness': freshness_page(state.source_rows, state.snapshot_summary, state.freshness),
        'recommendations': recommendation_content,
        'methodology': methodology_content,
    }

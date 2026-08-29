from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)

from .capacity.actions import build_capacity_action_state
from .capacity.charts import build_capacity_forecast_chart_svg, build_participation_donut_svg
from .capacity.forecast import build_capacity_forecast_state
from .capacity.model import build_capacity_state
from .capacity.sections import (
    build_compute_section,
    build_cover_section,
    build_executive_section,
    build_forecast_section,
    build_methodology_section,
    build_recommendation_section,
    build_risk_section,
    build_scheduling_section,
    build_storage_section,
)

_CAPACITY_PAGE_TITLES = (
    'Cover',
    'Executive Brief',
    'Compute Capacity',
    'Scheduling Capacity',
    'Storage Capacity',
    'Capacity Forecast',
    'Capacity Risk Register',
    'Recommendation Plan',
    'Methodology and Evidence Boundary',
)


def build_capacity_analysis_presentation(
    report: Any,
    payload: Mapping[str, Any],
    *,
    report_id: str,
    report_name: str,
    cluster_scope: str,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
    generated_at: str,
    generated_by: str,
    classification: str,
) -> dict[str, Any]:
    del report
    state = build_capacity_state(payload)
    forecast = build_capacity_forecast_state(state)
    actions = build_capacity_action_state(payload, state, forecast, period_label=period_label)
    forecast_chart = build_capacity_forecast_chart_svg(
        resources=state.resources,
        forecast_items=forecast.items,
        projections=forecast.projections,
    )
    donut_svg = build_participation_donut_svg(
        state.participation,
        state.ready_nodes,
        state.total_nodes,
    )

    return {
        'page_count': len(_CAPACITY_PAGE_TITLES),
        'presentation_version': 'v3.0-capacity-analysis-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'layout_contract': analytics_layout_contract(
            page_count=9,
            table_policy='concise-register-plus-reference',
            missing_evidence_policy='explicit-not-available',
        ),
        'report_id': report_id,
        'report_name': report_name,
        'report_title': 'Capacity Analysis',
        'report_subtitle': 'Kubernetes Operational Intelligence Report',
        'classification': classification,
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'page_titles': _CAPACITY_PAGE_TITLES,
        'cover': build_cover_section(state, cluster_scope),
        'executive': build_executive_section(state, forecast, actions),
        'compute': build_compute_section(state, forecast),
        'scheduling': build_scheduling_section(state, donut_svg),
        'storage': build_storage_section(state),
        'forecast': build_forecast_section(forecast, forecast_chart),
        'risks': build_risk_section(state, actions),
        'recommendations': build_recommendation_section(actions),
        'methodology': build_methodology_section(
            state,
            forecast,
            actions,
            namespace_scope,
            period_label,
            data_cutoff,
        ),
    }

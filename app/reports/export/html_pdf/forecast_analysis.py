from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)
from app.reports.export.html_pdf.builder_context import ReportDocumentContext

from .forecast.actions import build_recommendation_plan, build_source_rows
from .forecast.context import resolve_forecast_context
from .forecast.model import FORECAST_PAGE_TITLES, build_forecast_state
from .forecast.sections import (
    build_cover,
    build_executive,
    build_exposure,
    build_methodology,
    build_pod_storage,
    build_portfolio,
    build_resource_page,
)


def build_forecast_analysis_presentation(
    report_or_payload: Any,
    payload: Mapping[str, Any] | None = None,
    *,
    context: ReportDocumentContext | None = None,
    classification: str,
    **legacy_context: Any,
) -> dict[str, Any]:
    source = cast(Mapping[str, Any], report_or_payload) if payload is None else payload
    resolved_context = resolve_forecast_context(context, legacy_context)
    state = build_forecast_state(source)
    recommendations = build_recommendation_plan(state)
    sources = build_source_rows(state)

    return {
        'presentation_version': 'v3.0-forecast-analysis-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'page_count': len(FORECAST_PAGE_TITLES),
        'layout_contract': analytics_layout_contract(
            page_count=9,
            table_policy='concise-register-plus-reference',
            missing_evidence_policy='explicit-not-available',
            forecast_policy='committed-materialized-evidence-only',
        ),
        'report_id': resolved_context.report_id,
        'report_name': resolved_context.report_name,
        'report_title': 'Forecast Analysis',
        'cluster_scope': resolved_context.cluster_scope,
        'namespace_scope': resolved_context.namespace_scope,
        'period_label': resolved_context.period_label,
        'data_cutoff': resolved_context.data_cutoff,
        'generated_at': resolved_context.generated_at_label,
        'generated_by': resolved_context.generated_by_label,
        'classification': classification,
        'page_titles': FORECAST_PAGE_TITLES,
        'cover': build_cover(state),
        'executive': build_executive(state, recommendations),
        'portfolio': build_portfolio(state),
        'cpu': build_resource_page(state.resources['cpu'], 'CPU'),
        'memory': build_resource_page(state.resources['memory'], 'Memory'),
        'pod_storage': build_pod_storage(state),
        'exposure': build_exposure(state),
        'recommendations': recommendations,
        'methodology': build_methodology(
            state,
            sources=sources,
            period_label=resolved_context.period_label,
            data_cutoff=resolved_context.data_cutoff,
        ),
    }

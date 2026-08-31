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

from .alerts.actions import build_recommendations, correlation_rows, source_rows
from .alerts.context import resolve_alerts_context
from .alerts.model import build_alerts_state
from .alerts.sections import (
    build_active_alerts,
    build_anomalies,
    build_correlation,
    build_cover,
    build_executive,
    build_methodology,
    build_ownership,
    build_recommendations_section,
    build_severity_category,
)

_PAGE_COUNT = 9


def build_alerts_anomalies_presentation(
    report_or_payload: Any,
    payload: Mapping[str, Any] | None = None,
    *,
    context: ReportDocumentContext | None = None,
    classification: str,
    **legacy_context: Any,
) -> dict[str, Any]:
    source = cast(Mapping[str, Any], report_or_payload) if payload is None else payload
    resolved_context = resolve_alerts_context(context, legacy_context)
    state = build_alerts_state(source)
    recommendations = build_recommendations(state)
    correlations = correlation_rows(state)
    sources = source_rows(source)

    return {
        'presentation_version': 'v3.0-alerts-anomalies-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'page_count': _PAGE_COUNT,
        'layout_contract': analytics_layout_contract(
            page_count=9,
            table_policy='concise-register-plus-reference',
            correlation_policy='review-lead-not-causality',
            missing_evidence_policy='explicit-not-available',
        ),
        'report_id': resolved_context.report_id,
        'report_name': resolved_context.report_name,
        'report_title': 'Alerts and Anomalies',
        'cluster_scope': resolved_context.cluster_scope,
        'namespace_scope': resolved_context.namespace_scope,
        'period_label': resolved_context.period_label,
        'data_cutoff': resolved_context.data_cutoff,
        'generated_at': resolved_context.generated_at_label,
        'generated_by': resolved_context.generated_by_label,
        'classification': classification,
        'cover': build_cover(state),
        'executive': build_executive(state, recommendations),
        'severity_category': build_severity_category(state),
        'active_alerts': build_active_alerts(state),
        'anomalies': build_anomalies(state),
        'ownership': build_ownership(state),
        'correlation': build_correlation(state, correlations),
        'recommendations': build_recommendations_section(recommendations),
        'methodology': build_methodology(
            state,
            source_rows=sources,
            period_label=resolved_context.period_label,
            data_cutoff=resolved_context.data_cutoff,
        ),
    }

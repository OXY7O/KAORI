from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)
from app.reports.export.html_pdf.builder_context import ReportDocumentContext
from app.reports.export.html_pdf.utilization.actions import build_recommendations, build_source_rows
from app.reports.export.html_pdf.utilization.charts import build_utilization_charts
from app.reports.export.html_pdf.utilization.model import build_utilization_state
from app.reports.export.html_pdf.utilization.sections import (
    build_cover,
    build_cpu,
    build_distribution,
    build_executive,
    build_memory,
    build_methodology,
    build_pod_node,
    build_trend,
)

_RESOURCE_UTILIZATION_PAGE_TITLES = (
    'Cover',
    'Executive Brief',
    'CPU Utilization',
    'Memory Utilization',
    'Pod and Node Utilization',
    'Utilization Distribution',
    'Trend Evidence',
    'Recommendation Plan',
    'Methodology and Evidence Boundary',
)


def build_resource_utilization_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
    state = build_utilization_state(payload)
    charts = build_utilization_charts(state)
    source_rows = build_source_rows(state, context.period_label)

    return {
        'page_count': len(_RESOURCE_UTILIZATION_PAGE_TITLES),
        'presentation_version': 'v3.0-resource-utilization-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'layout_contract': analytics_layout_contract(
            page_count=9,
            table_policy='concise-register-plus-reference',
        ),
        'report_id': context.report_id,
        'report_name': context.report_name,
        'report_title': 'Resource Utilization',
        'report_subtitle': 'Kubernetes Operational Intelligence Report',
        'classification': classification,
        'cluster_scope': context.cluster_scope,
        'namespace_scope': context.namespace_scope,
        'period_label': context.period_label,
        'data_cutoff': context.data_cutoff,
        'generated_at': context.generated_at_label,
        'generated_by': context.generated_by_label,
        'page_titles': _RESOURCE_UTILIZATION_PAGE_TITLES,
        'cover': build_cover(state, cluster_scope=context.cluster_scope),
        'executive': build_executive(state, source_rows=source_rows),
        'cpu': build_cpu(state, chart_svg=charts['cpu']),
        'memory': build_memory(state, chart_svg=charts['memory']),
        'pod_node': build_pod_node(state),
        'distribution': build_distribution(state),
        'trend': build_trend(state, chart_svg=charts['trend']),
        'recommendations': build_recommendations(state),
        'methodology': build_methodology(
            state,
            source_rows=source_rows,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
        ),
        'storage_context': state.storage,
    }

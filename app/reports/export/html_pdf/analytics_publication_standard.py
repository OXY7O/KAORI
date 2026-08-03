from __future__ import annotations

from typing import Any

ANALYTICS_PUBLICATION_FAMILY = 'analytics'
ANALYTICS_PUBLICATION_STANDARD = 'kaori-analytics-pdf-v1.1'
ANALYTICS_CANONICAL_REFERENCE = 'analytics-overview-report-34'
ANALYTICS_VISUAL_STYLE = 'reporting-standard-v2.9.2-analytics-family'
ANALYTICS_SHARED_STYLESHEET = 'analytics_publication.css'

ANALYTICS_TEMPLATE_STYLESHEETS: dict[str, str] = {
    'reports/pdf/analytics_overview.html': 'analytics_overview.css',
    'reports/pdf/resource_utilization.html': 'resource_utilization.css',
    'reports/pdf/capacity_analysis.html': 'capacity_analysis.css',
    'reports/pdf/storage_analysis.html': 'storage_analysis.css',
    'reports/pdf/workload_analysis.html': 'workload_analysis.css',
    'reports/pdf/forecast_analysis.html': 'forecast_analysis.css',
    'reports/pdf/top_consumers_analysis.html': 'top_consumers_analysis.css',
    'reports/pdf/alerts_anomalies.html': 'alerts_anomalies.css',
}

ANALYTICS_TEMPLATE_NAMES = tuple(ANALYTICS_TEMPLATE_STYLESHEETS)


def analytics_layout_contract(
    *,
    page_count: int,
    table_policy: str,
    **overrides: Any,
) -> dict[str, Any]:
    """Return the shared KAORI Analytics PDF layout contract.

    Report modules provide only evidence-specific policies. Reusable visual
    behavior stays centralized here so new Analytics reports cannot drift from
    the approved publication standard.
    """

    contract: dict[str, Any] = {
        'paper': 'A4 Portrait',
        'page_count': page_count,
        'fixed_page_canvas': True,
        'status_style': 'plain-colored-text',
        'table_policy': table_policy,
        'cover_header_policy': 'symmetric-two-sided',
        'section_separator_policy': 'none',
        'section_rhythm': 'title-subtitle-content',
        'table_alignment': 'left-middle',
        'methodology_layout': 'parallel-registers',
        'visual_style': ANALYTICS_VISUAL_STYLE,
    }
    contract.update(overrides)
    return contract

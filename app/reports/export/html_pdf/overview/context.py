from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)

ANALYTICS_PAGE_TITLES = (
    'Cover',
    'Executive Brief',
    'Resource Posture',
    'Trend & Forecast',
    'Top Consumers',
    'Capacity Pressure',
    'Alerts & Anomalies',
    'Reporting Summary',
    'Inventory Snapshot',
    'Data Freshness & Reliability',
    'Recommendation Plan',
    'Methodology & Evidence Boundary',
)


@dataclass(frozen=True, slots=True)
class OverviewContext:
    report: Any
    payload: Mapping[str, Any]
    report_id: str
    report_name: str
    cluster_scope: str
    namespace_scope: str
    period_label: str
    data_cutoff: str
    generated_at: str
    generated_by: str
    classification: str
    overall_posture: str
    overall_tone: str


def common_presentation(context: OverviewContext) -> dict[str, Any]:
    return {
        'page_count': len(ANALYTICS_PAGE_TITLES),
        'presentation_version': 'v3.0-analytics-overview-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'layout_contract': analytics_layout_contract(
            page_count=len(ANALYTICS_PAGE_TITLES),
            table_policy='concise-register-plus-reference',
            section_page_breaks=True,
            truncate_identities=False,
            identity_policy='reference-register',
        ),
        'report_id': context.report_id,
        'report_name': context.report_name,
        'report_title': 'Analytics Overview',
        'report_subtitle': 'Kubernetes Operational Intelligence Report',
        'classification': context.classification,
        'cluster_scope': context.cluster_scope,
        'namespace_scope': context.namespace_scope,
        'period_label': context.period_label,
        'data_cutoff': context.data_cutoff,
        'generated_at': context.generated_at,
        'generated_by': context.generated_by,
        'page_titles': ANALYTICS_PAGE_TITLES,
    }

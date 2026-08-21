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
from app.reports.export.html_pdf.normalization import sanitize_text


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def build_object_storage_analysis_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
    """Build the provider-neutral Object Storage Analytics PDF presentation contract."""

    metrics_source = _mapping(payload.get('metrics_source'))
    metrics_readiness = _mapping(payload.get('metrics_readiness'))
    page_count = 1 + len(context.sections)

    return {
        'presentation_version': 'v3.0-object-storage-overview-standard',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'layout_contract': analytics_layout_contract(
            page_count=page_count,
            table_policy='concise-register-plus-reference',
            dynamic_section_policy='selected-report-sections',
        ),
        'report_id': context.report_id,
        'report_name': context.report_name,
        'report_title': 'Object Storage Operational Intelligence',
        'classification': classification,
        'page_count': page_count,
        'scope_value': context.cluster_scope,
        'period_label': context.period_label,
        'data_cutoff': context.data_cutoff,
        'generated_at': context.generated_at_label,
        'generated_by': context.generated_by_label,
        'source_label': sanitize_text(
            metrics_source.get('provider_label') or metrics_source.get('label'),
            fallback='Object Storage Evidence',
        ),
        'metrics_contract': sanitize_text(
            metrics_readiness.get('label') or metrics_readiness.get('status'),
            fallback='Evidence Boundary Recorded',
        ),
    }

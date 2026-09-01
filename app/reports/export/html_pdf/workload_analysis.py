from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)

from .workload import build_workload_context, build_workload_presentation
from .workload.presentation import PAGE_COUNT


def build_workload_analysis_presentation(
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
    context = build_workload_context(
        report,
        payload,
        report_id=report_id,
        report_name=report_name,
        cluster_scope=cluster_scope,
        namespace_scope=namespace_scope,
        period_label=period_label,
        data_cutoff=data_cutoff,
        generated_at=generated_at,
        generated_by=generated_by,
        classification=classification,
    )
    presentation = build_workload_presentation(context)
    return {**presentation, **_publication_contract()}


def _publication_contract() -> dict[str, Any]:
    return {
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'layout_contract': analytics_layout_contract(
            page_count=PAGE_COUNT,
            table_policy='concise-register-plus-reference',
            missing_evidence_policy='explicit-not-available',
        ),
    }


__all__ = ['build_workload_analysis_presentation']

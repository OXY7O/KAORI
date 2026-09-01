from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.reports.export.html_pdf.builder_context import ReportDocumentContext


@dataclass(frozen=True, slots=True)
class LegacyUtilizationPresentationContext:
    report_id: str
    report_name: str
    cluster_scope: str
    namespace_scope: str
    period_label: str
    data_cutoff: str
    generated_at_label: str
    generated_by_label: str


def resolve_utilization_context(
    context: ReportDocumentContext | None,
    legacy: Mapping[str, Any],
) -> ReportDocumentContext | LegacyUtilizationPresentationContext:
    if context is not None:
        return context
    return LegacyUtilizationPresentationContext(
        report_id=str(legacy.get('report_id') or ''),
        report_name=str(legacy.get('report_name') or ''),
        cluster_scope=str(legacy.get('cluster_scope') or ''),
        namespace_scope=str(legacy.get('namespace_scope') or ''),
        period_label=str(legacy.get('period_label') or ''),
        data_cutoff=str(legacy.get('data_cutoff') or ''),
        generated_at_label=str(legacy.get('generated_at') or ''),
        generated_by_label=str(legacy.get('generated_by') or ''),
    )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.reports.export.constants import REPORT_DOMAIN_LABELS, SOURCE_KIND_LABELS
from app.reports.export.html_pdf.document import ReportDocument, ReportMetric, ReportSection
from app.reports.export.html_pdf.normalization import sanitize_text


@dataclass(frozen=True, slots=True)
class ReportDocumentContext:
    generated_at: datetime
    selected_sections: list[str]
    source_metrics: tuple[ReportMetric, ...]
    overall_posture: str
    overall_tone: str
    sections: list[ReportSection]
    generated_by_label: str
    cluster_scope: str
    namespace_scope: str
    internal_report_id: str
    report_id: str
    report_name: str
    report_type_spec: Any
    report_type_label: str
    period_label: str
    generated_at_label: str
    data_cutoff: str


def finalize_report_document(
    report: Any,
    context: ReportDocumentContext,
    *,
    template_name: str,
    presentation: dict[str, Any],
    classification: str,
    retention_days: int,
) -> ReportDocument:
    return ReportDocument(
        report_id=context.report_id,
        report_name=context.report_name,
        report_type_label=context.report_type_label,
        report_description=context.report_type_spec.description,
        report_domain_label=REPORT_DOMAIN_LABELS.get(
            getattr(report, 'report_domain', ''),
            'KAORI Kubernetes Reports',
        ),
        source_kind_label=SOURCE_KIND_LABELS.get(getattr(report, 'source_kind', ''), 'Kubernetes'),
        cluster_scope=context.cluster_scope,
        namespace_scope=context.namespace_scope,
        period_label=context.period_label,
        generated_at=context.generated_at_label,
        data_cutoff=context.data_cutoff,
        generated_by=context.generated_by_label,
        classification=classification,
        retention_label=f'{max(retention_days, 0)} Days' if retention_days > 0 else 'Policy Managed',
        overall_posture=context.overall_posture,
        overall_tone=context.overall_tone,
        source_metrics=context.source_metrics,
        sections=tuple(context.sections),
        methodology_notes=(
            'Report content follows the section order saved by the existing KAORI Template System.',
            'Data is collected before rendering. The HTML template and WeasyPrint renderer do not query external systems directly.',
            'Unavailable sources are shown as report limitations and are excluded from conclusions that require live evidence.',
            'Critical operational decisions should be verified against live infrastructure evidence and the related JobExecution record.',
        ),
        template_label=f'{context.report_type_label} Template',
        template_name=template_name,
        presentation=presentation,
        metadata={
            'section_count': len(context.sections),
            'internal_report_id': context.internal_report_id,
            'report_reference': context.report_id,
            'selected_section_keys': context.selected_sections,
            'output_format': sanitize_text(getattr(report, 'output_format', None), fallback='Not Available').upper(),
        },
    )

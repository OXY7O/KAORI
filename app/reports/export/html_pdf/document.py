from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReportMetric:
    label: str
    value: str
    note: str = ''
    tone: str = 'neutral'


@dataclass(frozen=True)
class ReportFinding:
    title: str
    description: str = ''
    tone: str = 'neutral'


@dataclass(frozen=True)
class ReportTable:
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    note: str = ''


@dataclass(frozen=True)
class ReportSection:
    key: str
    number: int
    title: str
    description: str
    status_label: str = ''
    status_tone: str = 'neutral'
    metrics: tuple[ReportMetric, ...] = ()
    findings: tuple[ReportFinding, ...] = ()
    tables: tuple[ReportTable, ...] = ()
    chart_svg: str = ''
    note: str = ''
    page_orientation: str = 'portrait'

    @property
    def anchor(self) -> str:
        return f'section-{self.number:02d}-{self.key.replace("_", "-")}'


@dataclass(frozen=True)
class ReportDocument:
    report_id: str
    report_name: str
    report_type_label: str
    report_description: str
    report_domain_label: str
    source_kind_label: str
    cluster_scope: str
    namespace_scope: str
    period_label: str
    generated_at: str
    data_cutoff: str
    generated_by: str
    classification: str
    retention_label: str
    overall_posture: str
    overall_tone: str
    source_metrics: tuple[ReportMetric, ...]
    sections: tuple[ReportSection, ...]
    methodology_notes: tuple[str, ...]
    template_label: str
    renderer_label: str = 'WeasyPrint HTML/PDF'
    template_name: str = 'reports/pdf/report.html'
    presentation: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

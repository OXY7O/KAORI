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
from app.reports.export.html_pdf.storage.actions import (
    executive_findings,
    recommendation_cards,
    recommendation_plan,
    risk_register,
)
from app.reports.export.html_pdf.storage.model import node_count, normalize_storage_input
from app.reports.export.html_pdf.storage.records import (
    capacity_resource,
    count_risk_rows,
    expansion_evidence_available,
    filesystem_records,
    persistent_claim_summary,
    persistent_volume_summary,
)
from app.reports.export.html_pdf.storage.sections import (
    capacity_section,
    cover_section,
    executive_section,
    filesystem_section,
    methodology_section,
    persistent_section,
    recommendations_section,
    risk_section,
    trend_section,
)
from app.reports.export.html_pdf.storage.trend import storage_trend


def build_storage_analysis_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
    source = normalize_storage_input(payload)
    capacity = capacity_resource(source.filesystem_summary, source.filesystem_rows)
    filesystem = filesystem_records(source.filesystem_rows)
    pv_summary = persistent_volume_summary(source.pv, source.pv_rows)
    pvc_summary = persistent_claim_summary(source.pvc, source.pvc_rows)
    local_risks = count_risk_rows(source.filesystem_rows)
    pvc_risks = count_risk_rows(source.pvc_rows)
    pv_risks = count_risk_rows(source.pv_rows)
    cards = recommendation_cards(payload)
    trend = storage_trend(payload, current=capacity['used_percent'])
    expansion_available = expansion_evidence_available(source.pv_rows, source.pvc_rows)
    nodes = node_count(payload, source.filesystem)
    evidence_gap_count = sum(
        1
        for available in (
            capacity['evidence_available'],
            bool(filesystem),
            pv_summary['evidence_available'],
            pvc_summary['evidence_available'],
            trend['available'],
        )
        if not available
    )
    findings = executive_findings(
        capacity=capacity,
        local_risks=local_risks,
        filesystem_available=bool(filesystem),
        pvc_available=pvc_summary['evidence_available'],
        pv_available=pv_summary['evidence_available'],
    )
    risks = risk_register(
        capacity=capacity,
        local_risks=local_risks,
        filesystem_available=bool(filesystem),
        pvc_risks=pvc_risks,
        pvc_available=pvc_summary['evidence_available'],
        pv_risks=pv_risks,
        expansion_available=expansion_available,
    )
    recommendations = recommendation_plan(
        recommendation_cards=cards,
        risk_register=risks,
        capacity=capacity,
    )
    return {
        'presentation_version': 'v3.0-storage-analysis-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'page_count': 9,
        'layout_contract': analytics_layout_contract(
            page_count=9,
            table_policy='concise-register-plus-reference',
            missing_evidence_policy='explicit-not-available',
        ),
        'report_id': context.report_id,
        'report_name': context.report_name,
        'cluster_scope': context.cluster_scope,
        'namespace_scope': context.namespace_scope,
        'period_label': context.period_label,
        'data_cutoff': context.data_cutoff,
        'generated_at': context.generated_at_label,
        'generated_by': context.generated_by_label,
        'classification': classification,
        'cover': cover_section(source.cluster),
        'executive': executive_section(
            capacity=capacity,
            local_risks=local_risks,
            evidence_gap_count=evidence_gap_count,
            findings=findings,
        ),
        'capacity': capacity_section(capacity),
        'filesystem': filesystem_section(
            capacity=capacity,
            filesystem_summary=source.filesystem_summary,
            filesystem_records=filesystem,
            node_count=nodes,
        ),
        'persistent': persistent_section(
            pv_summary=pv_summary,
            pvc_summary=pvc_summary,
            pv_rows=source.pv_rows,
            pvc_rows=source.pvc_rows,
        ),
        'risk': risk_section(
            local_risks=local_risks,
            actionable_count=sum(1 for item in cards if item['actionable']),
            risk_register=risks,
            expansion_available=expansion_available,
        ),
        'trend': trend_section(capacity=capacity, trend=trend),
        'recommendations': recommendations_section(recommendations),
        'methodology': methodology_section(
            payload=payload,
            evidence_gap_count=evidence_gap_count,
            node_count=nodes,
            namespace_scope=context.namespace_scope,
            period_label=context.period_label,
            data_cutoff=context.data_cutoff,
        ),
    }

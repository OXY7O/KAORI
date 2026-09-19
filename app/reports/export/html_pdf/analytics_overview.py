from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)
from .overview.context import ANALYTICS_PAGE_TITLES, OverviewContext
from .overview.presentation import build_overview_presentation


def build_analytics_overview_presentation(
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
    overall_posture: str,
    overall_tone: str,
) -> dict[str, Any]:
    presentation = build_overview_presentation(
        OverviewContext(
            report=report,
            payload=payload,
            report_id=report_id,
            report_name=report_name,
            cluster_scope=cluster_scope,
            namespace_scope=namespace_scope,
            period_label=period_label,
            data_cutoff=data_cutoff,
            generated_at=generated_at,
            generated_by=generated_by,
            classification=classification,
            overall_posture=overall_posture,
            overall_tone=overall_tone,
        )
    )
    return {**presentation, **_publication_contract()}


def _publication_contract() -> dict[str, Any]:
    return {
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
    }

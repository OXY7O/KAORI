from __future__ import annotations

from typing import Any

ANALYTICS_PUBLICATION_FAMILY = 'analytics'
ANALYTICS_PUBLICATION_STANDARD = 'kaori-analytics-pdf-v3.0'
ANALYTICS_CANONICAL_REFERENCE = 'kaori-analytics-publication-v3'
ANALYTICS_VISUAL_STYLE = 'kaori-publication-v3-neutral-evidence-first'
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
    'reports/pdf/object_storage_analysis.html': 'object_storage_analysis.css',
    'reports/pdf/analytics_unavailable.html': 'analytics_unavailable.css',
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
        'dynamic_identity_policy': 'reference-register',
        'table_row_policy': 'fixed-comparison-fields',
        'chart_label_policy': 'collision-safe-gutter',
        'paragraph_rhythm': 'tokenized',
        'section_description_policy': 'concise-helper-max-72',
        'paired_layout_policy': 'symmetric-50-50-or-stack',
        'peer_alignment_policy': 'shared-title-helper-body-rows',
        'peer_section_flow_policy': 'block-grid-owned-alignment',
        'peer_helper_slot': '7mm',
        'section_spacing_policy': '5.6mm',
        'first_section_clearance_policy': 'canonical-gap-even-after-non-section-block',
        'top_level_flow_policy': 'publication-block-owns-outer-gap',
        'publication_stack_policy': 'outer-5.6mm-inner-5.6mm',
        'chart_spacing_policy': 'internal-only-no-next-section-clearance',
        'shared_component_spacing_policy': 'summary-cards-and-chart-legends-global',
        'paired_section_clearance_policy': 'single-5.6mm-section-gap-no-double-spacing',
        'visual_box_policy': 'locked-size-tokens-content-scales-inside',
        'footer_safe_zone': '18mm',
        'paragraph_spacing_policy': '2.2mm',
        'global_rhythm_owner_policy': 'shared-stylesheet-only',
        'dense_page_policy': 'compact-internal-chrome-never-typography',
        'chart_identity_policy': 'stable-reference-codes-only',
        'dynamic_page_policy': 'content-budgeted',
        'section_continuation_policy': 'same-section-only',
        'table_overflow_policy': 'chunk-with-repeated-header',
        'reference_layout_policy': 'two-column-or-stack',
        'typography_scaling_policy': 'never-for-density',
        'dynamic_pair_policy': 'density-selects-50-50-or-stack',
        'public_reference_policy': 'family-type-date-fingerprint',
        'visual_style': ANALYTICS_VISUAL_STYLE,
    }
    contract.update(overrides)
    return contract

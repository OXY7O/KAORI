from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PDF_TEMPLATE_DIR = ROOT / 'app/templates/reports/pdf'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def _literal_section_descriptions(source: str) -> list[tuple[str, str | None]]:
    pattern = re.compile(
        r"(?:ui\.)?section\(\s*'([^']+)'(?:\s*,\s*'([^']*)')?",
        flags=re.MULTILINE,
    )
    return [(title, subtitle or None) for title, subtitle in pattern.findall(source)]


def test_shared_publication_css_owns_editorial_typography_and_rhythm() -> None:
    css = read('app/static/reports/pdf/analytics_publication.css')
    compact = ''.join(css.split())

    for token in (
        '--analytics-type-section:10.2pt',
        '--analytics-type-subheading:8.2pt',
        '--analytics-type-body:8pt',
        '--analytics-type-support:6.65pt',
        '--analytics-rhythm-title-description:1.45mm',
        '--analytics-rhythm-description-content:3mm',
        '--analytics-rhythm-paragraph:2.2mm',
        '--analytics-rhythm-register-reference:3.6mm',
        '--analytics-rhythm-section:5.6mm',
    ):
        assert token in compact

    assert 'KAORIAnalyticsPublicationRhythmLock' in compact
    assert 'font-size:var(--analytics-type-section)' in compact
    assert 'margin:var(--analytics-rhythm-title-description)00' in compact
    assert 'margin-top:var(--analytics-rhythm-description-content)' in compact
    assert 'margin-top:var(--analytics-rhythm-register-reference)' in compact
    assert 'margin-top:var(--analytics-rhythm-section)' in compact
    assert 'grid-template-columns:minmax(0,1fr)minmax(0,1fr)' in compact


def test_all_analytics_sections_use_short_descriptions() -> None:
    missing: list[str] = []
    too_long: list[str] = []

    for path in sorted(PDF_TEMPLATE_DIR.glob('*.html')):
        source = path.read_text(encoding='utf-8')
        for title, subtitle in _literal_section_descriptions(source):
            if subtitle is None or not subtitle.strip():
                missing.append(f'{path.name}: {title}')
                continue
            if len(subtitle) > 72:
                too_long.append(f'{path.name}: {title} ({len(subtitle)})')

    assert not missing, 'Missing section descriptions:\n' + '\n'.join(missing)
    assert not too_long, 'Section descriptions exceed 72 characters:\n' + '\n'.join(too_long)


def test_overview_figure_numbering_is_contiguous_for_visual_evidence() -> None:
    template = read('app/templates/reports/pdf/analytics_overview.html')
    expected = (
        'Figure 1 - Memory Demand Forecast',
        'Figure 2 - Leading Consumer Signals',
        'Figure 3 - Alert Profile',
        'Figure 4 - Report Status Distribution',
        'Figure 5 - Freshness Over Time',
    )
    positions = [template.index(title) for title in expected]
    assert positions == sorted(positions)
    assert "section('Alert Profile'" not in template
    assert "section('Figure 3 - Report Status Distribution'" not in template
    assert "section('Figure 4 - Freshness Over Time'" not in template


def test_resource_utilization_decision_and_interpretation_sections_have_helpers() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')
    for expected in (
        "section('Management Decision', 'Decision boundary for displayed CPU consumer evidence.')",
        "section('Management Decision', 'Decision boundary for displayed memory consumer evidence.')",
        "section('Operational Interpretation', 'Scheduling headroom and node participation conclusion.')",
        "section('Management Interpretation', 'Management conclusion for displayed concentration evidence.')",
        "section('Management Interpretation', 'Planning conclusion for the committed trend horizon.')",
        "section('Methodology References', 'Threshold, forecast, and utilization-basis rules.')",
        "section('Limitations and Status Language', 'Operational constraints and unavailable-evidence states.')",
    ):
        assert expected in template


def test_shared_stylesheet_is_loaded_after_report_specific_css() -> None:
    shared = read('app/static/reports/pdf/analytics_publication.css')
    engine_path = ROOT / 'app/reports/export/html_pdf/engine.py'
    if not engine_path.exists():
        pytest.skip('Partial patch workspace does not contain the canonical engine module.')
    engine = engine_path.read_text(encoding='utf-8')

    assert 'KAORI Analytics Publication Rhythm Lock' in shared
    assert 'Report-specific CSS is loaded first' in engine
    assert 'Analytics standard is loaded last' in engine


def test_publication_verifier_enforces_rhythm_and_concise_descriptions() -> None:
    verifier = read('scripts/verify_analytics_pdf_publication.py')

    assert 'SECTION_DESCRIPTION_MAX_CHARS = 72' in verifier
    assert 'Missing section description' in verifier
    assert 'Section description exceeds {SECTION_DESCRIPTION_MAX_CHARS} characters' in verifier
    assert '--analytics-rhythm-section:5.6mm' in verifier
    assert '--analytics-rhythm-pair-clearance:0mm' in verifier
    assert 'KAORI Analytics Publication Rhythm Lock' in verifier
    assert 'KAORI Analytics Publication R6 - Clean Sweep' in verifier
    assert 'Report CSS overrides canonical top-level section rhythm' in verifier
    assert 'Report CSS overrides canonical subheading rhythm' in verifier


def test_layout_contract_and_docs_publish_the_family_rhythm_policy() -> None:
    standard = read('app/reports/export/html_pdf/analytics_publication_standard.py')
    docs = read('docs/reports/kaori-analytics-pdf-publication-standard-v3.md')

    for token in (
        "'section_description_policy': 'concise-helper-max-72'",
        "'paired_layout_policy': 'symmetric-50-50-or-stack'",
        "'section_spacing_policy': '5.6mm'",
        "'paired_section_clearance_policy': 'single-5.6mm-section-gap-no-double-spacing'",
        "'visual_box_policy': 'locked-size-tokens-content-scales-inside'",
        "'footer_safe_zone': '18mm'",
        "'paragraph_spacing_policy': '2.2mm'",
        "'global_rhythm_owner_policy': 'shared-stylesheet-only'",
        "'dense_page_policy': 'compact-internal-chrome-never-typography'",
        "'chart_identity_policy': 'stable-reference-codes-only'",
    ):
        assert token in standard

    assert 'Family editorial rhythm lock (2026-08-25)' in docs
    assert 'Section helper descriptions should remain at or below 72 characters' in docs
    assert '50/50' in docs
    assert 'stack the blocks vertically' in docs
    assert 'Paired sections never add a second clearance layer' in docs
    assert 'Report-specific CSS must not own top-level section spacing' in docs
    assert 'Dense pages compact internal chrome before typography' in docs
    assert 'Chart labels use stable reference codes' in docs


def test_family_pairs_reserve_bottom_clearance_and_align_descriptions() -> None:
    css = read('app/static/reports/pdf/analytics_publication.css')
    compact = ''.join(css.split())
    assert '--analytics-rhythm-pair-clearance:0mm' in compact
    assert 'padding-bottom:0!important' in compact
    assert '.page-content>.two-column' in compact
    assert 'margin-top:var(--analytics-rhythm-section)' in compact
    assert '.two-column>.content-section>.section-subtitle' in compact
    assert 'min-height:0!important' in compact


def test_workload_half_width_signal_register_uses_compact_labels() -> None:
    presenter = read('app/reports/export/html_pdf/workload_analysis.py')
    copy_rules = read('app/reports/export/html_pdf/publication_copy.py')
    assert 'compact_governance_signal' in presenter
    for label in ('ResourceQuota Gap', 'Requests Gap', 'Memory Limit Review', 'BestEffort Review'):
        assert label in copy_rules


def test_storage_trend_avoids_start_and_cutoff_label_collision() -> None:
    presenter = read('app/reports/export/html_pdf/storage_analysis.py')
    assert 'compact_axis_labels = cutoff_x - left < 70' in presenter
    assert "if not compact_axis_labels" in presenter


def test_resource_utilization_interpretation_sections_render_body_copy() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')
    assert '<p>{{ p.pod_node.interpretation }}</p>' in template
    assert '<p>{{ p.trend.interpretation }}</p>' in template


def test_shared_rhythm_has_single_spacing_owner_without_pair_double_gap() -> None:
    css = read('app/static/reports/pdf/analytics_publication.css')
    compact = ''.join(css.split())
    assert '--analytics-footer-safe-zone:18mm' in compact
    assert '--analytics-visual-pair-height:50mm' in compact
    assert '--analytics-visual-distribution-height:48mm' in compact
    assert '--analytics-visual-wide-height:66mm' in compact
    assert 'padding-bottom:0!important' in compact
    assert '.metric-strip+.two-column' in compact
    assert 'margin-top:0!important' in compact
    assert '.two-column>.content-section>.section-subtitle' in compact
    assert 'min-height:0!important' in compact
    assert '.publication-stack{display:grid' in compact
    assert '.page-content>.metric-strip+.content-section' in compact
    assert '.publication-pair>.content-section:first-of-type{margin-top:0!important;' in compact


def test_graphic_boxes_use_publication_size_tokens() -> None:
    css = read('app/static/reports/pdf/analytics_publication.css')
    compact = ''.join(css.split())
    for selector_token in (
        '.kaori-resource-utilization-report.page-cpu.chart-frame',
        '.kaori-resource-utilization-report.page-distribution.memory-concentration-card',
        '.kaori-forecast-analysis-report.resource-chart',
        '.kaori-capacity-analysis-report.forecast-chart-frame',
        '.kaori-storage-analysis-report.storage-trend-frame',
    ):
        assert selector_token in compact
    assert 'height:var(--analytics-visual-pair-height)!important' in compact
    assert 'height:var(--analytics-visual-distribution-height)!important' in compact
    assert 'height:var(--analytics-visual-wide-height)!important' in compact


def test_overview_uses_shared_status_language_component() -> None:
    template = read('app/templates/reports/pdf/analytics_overview.html')
    assert '{{ ui.status_language(p.methodology.status_language) }}' in template
    assert 'status-legend-grid' not in template


def test_workload_signal_labels_do_not_depend_on_counts() -> None:
    presenter = read('app/reports/export/html_pdf/workload_analysis.py')
    copy_rules = read('app/reports/export/html_pdf/publication_copy.py')
    assert "'Without ResourceQuota': 'ResourceQuota Gap'" in copy_rules
    assert "'With Incomplete Requests': 'Requests Gap'" in copy_rules
    assert "'Need Memory Limit Review': 'Memory Limit Review'" in copy_rules
    assert "'BestEffort Workloads': 'BestEffort Review'" in copy_rules
    assert "compact_governance_signal(item['title'])" in presenter


def test_storage_count_donut_wraps_long_center_label() -> None:
    presenter = read('app/reports/export/html_pdf/storage_analysis.py')
    visuals = read('app/reports/export/html_pdf/publication_visuals.py')
    assert 'count_donut_svg' in presenter
    assert '_donut_label_lines(label)' in visuals
    assert '<tspan' in visuals
    assert 'font-size="7"' in visuals
    assert 'y="103"' in visuals


def test_top_consumer_totals_normalize_memory_before_display() -> None:
    presenter = read('app/reports/export/html_pdf/top_consumers_analysis.py')
    assert 'def _normalized_usage_value(' in presenter
    assert "_normalized_usage_value(row)" in presenter


def test_top_consumer_namespace_register_allocates_all_six_columns() -> None:
    css = read('app/static/reports/pdf/top_consumers_analysis.css')
    compact = ''.join(css.split())
    assert '.namespace-registerth:nth-child(6)' in compact
    widths = re.findall(r'\.namespace-registerth:nth-child\(\d+\)\{width:(\d+)%', compact)
    assert len(widths) == 6
    assert sum(map(int, widths)) == 100


REPORT_SPECIFIC_CSS = (
    'analytics_overview.css',
    'resource_utilization.css',
    'capacity_analysis.css',
    'storage_analysis.css',
    'workload_analysis.css',
    'forecast_analysis.css',
    'top_consumers_analysis.css',
    'alerts_anomalies.css',
    'object_storage_analysis.css',
)


def test_report_specific_css_does_not_override_global_section_rhythm() -> None:
    offenders: list[str] = []
    direct_section = re.compile(r'\.page[-\w]+\s+\.content-section\s*\{[^}]*margin-top\s*:', re.S)
    direct_body = re.compile(r'\.page[-\w]+\s+\.section-body\s*\{[^}]*margin-top\s*:', re.S)
    global_subheading = re.compile(r'(?m)^\.subheading\s*\{[^}]*margin\s*:')

    for name in REPORT_SPECIFIC_CSS:
        source = read(f'app/static/reports/pdf/{name}')
        if direct_section.search(source):
            offenders.append(f'{name}: page content-section margin')
        if direct_body.search(source):
            offenders.append(f'{name}: page section-body margin')
        if global_subheading.search(source):
            offenders.append(f'{name}: global subheading margin')

    assert not offenders, 'Report CSS must not own global publication rhythm:\n' + '\n'.join(offenders)


def test_shared_css_has_final_clean_sweep_rhythm_owner() -> None:
    css = read('app/static/reports/pdf/analytics_publication.css')
    compact = ''.join(css.split())
    assert 'KAORIAnalyticsPublicationR6-CleanSweep' in compact
    assert '.page-content>.content-section{margin-top:var(--analytics-rhythm-section)!important;}' in compact
    assert '.page-content>.two-column{margin-top:var(--analytics-rhythm-section)!important;}' in compact
    assert '.page-content>.paired-sections{margin-top:var(--analytics-rhythm-section)!important;}' in compact
    assert '.metric-strip+.content-section' in compact
    assert '.metric-strip+.two-column' in compact
    assert 'margin-top:0!important' in compact


def test_dense_storage_and_alert_pages_compact_internals_not_typography() -> None:
    storage_css = read('app/static/reports/pdf/storage_analysis.css')
    alert_css = read('app/static/reports/pdf/alerts_anomalies.css')

    assert '.page-persistent .report-table th,' in storage_css
    assert '.page-persistent .report-table td' in storage_css
    assert 'padding: 1.15mm 2mm;' in storage_css
    assert '.page-persistent .persistent-identities .identity-item' in storage_css
    assert 'padding-top: .75mm;' in storage_css

    assert '.page-active-alerts .report-table th,' in alert_css
    assert '.page-active-alerts .report-table td' in alert_css
    assert 'padding: 1.15mm 2mm;' in alert_css
    assert '.page-active-alerts .identity-item' in alert_css
    assert 'padding-top: .75mm;' in alert_css
    assert '.page-active-alerts .alert-references .reference-item' in alert_css


def test_top_consumer_namespace_charts_use_reference_codes() -> None:
    presenter = read('app/reports/export/html_pdf/top_consumers_analysis.py')
    template = read('app/templates/reports/pdf/top_consumers_analysis.html')

    assert "cpu_namespace_rows = [item for item in namespace_rows if item['signal'] == 'CPU']" in presenter
    assert "memory_namespace_rows = [item for item in namespace_rows if item['signal'] == 'Memory']" in presenter
    assert "'cpu_rows': cpu_namespace_rows" in presenter
    assert "'memory_rows': memory_namespace_rows" in presenter
    assert template.count('<strong>{{ item.ref }}</strong>') >= 2
    assert '<strong>{{ item.namespace }}</strong>' not in template


def test_top_consumer_resource_totals_use_normalized_values_everywhere() -> None:
    presenter = read('app/reports/export/html_pdf/top_consumers_analysis.py')
    assert "total = sum(_normalized_usage_value(row) for row in rows)" in presenter
    assert "memory_total = sum(_normalized_usage_value(row) for row in memory_rows)" in presenter
    assert "bucket['value'] += _normalized_usage_value(row)" in presenter


def test_report_specific_css_does_not_override_shared_publication_typography() -> None:
    canonical_selectors = (
        '.page-title-copy',
        '.content-section h2',
        '.content-section h3',
        '.section-subtitle',
        '.section-body',
        '.reference-helper',
        '.identity-register-subtitle',
        '.reference-item strong',
        '.reference-item p',
        '.identity-title',
        '.identity-meta',
        '.reference-code',
        '.metric > span',
        '.metric > strong',
        '.metric > em',
        '.report-table',
    )
    offenders: list[str] = []
    block_pattern = re.compile(r'([^{}]+)\{([^{}]*)\}', re.S)

    for name in REPORT_SPECIFIC_CSS:
        source = read(f'app/static/reports/pdf/{name}')
        for selector, declarations in block_pattern.findall(source):
            if not any(token in selector for token in canonical_selectors):
                continue
            if re.search(r'\b(?:font-size|line-height)\s*:', declarations):
                offenders.append(f'{name}: typography in {selector.strip()}')
            if any(token in selector for token in ('.reference-helper', '.identity-register-subtitle', '.section-subtitle', '.section-body')) and re.search(
                r'\bmargin(?:-top|-bottom)?\s*:', declarations
            ):
                offenders.append(f'{name}: rhythm in {selector.strip()}')

    assert not offenders, 'Shared publication CSS must own canonical typography/rhythm:\n' + '\n'.join(offenders)

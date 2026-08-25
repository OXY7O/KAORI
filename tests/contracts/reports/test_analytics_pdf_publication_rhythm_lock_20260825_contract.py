from __future__ import annotations

import re
from pathlib import Path

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
    engine = read('app/reports/export/html_pdf/engine.py')

    assert 'KAORI Analytics Publication Rhythm Lock' in shared
    assert 'Report-specific CSS is loaded first' in engine
    assert 'Analytics standard is loaded last' in engine


def test_publication_verifier_enforces_rhythm_and_concise_descriptions() -> None:
    verifier = read('scripts/verify_analytics_pdf_publication.py')

    assert 'SECTION_DESCRIPTION_MAX_CHARS = 72' in verifier
    assert 'Missing section description' in verifier
    assert 'Section description exceeds {SECTION_DESCRIPTION_MAX_CHARS} characters' in verifier
    assert '--analytics-rhythm-section:5.6mm' in verifier
    assert '--analytics-rhythm-pair-clearance:5.6mm' in verifier
    assert 'KAORI Analytics Publication Rhythm Lock' in verifier


def test_layout_contract_and_docs_publish_the_family_rhythm_policy() -> None:
    standard = read('app/reports/export/html_pdf/analytics_publication_standard.py')
    docs = read('docs/reports/kaori-analytics-pdf-publication-standard-v3.md')

    for token in (
        "'section_description_policy': 'concise-helper-max-72'",
        "'paired_layout_policy': 'symmetric-50-50-or-stack'",
        "'section_spacing_policy': '5.6mm'",
        "'paired_section_clearance_policy': '5.6mm'",
        "'paragraph_spacing_policy': '2.2mm'",
    ):
        assert token in standard

    assert 'Family editorial rhythm lock (2026-08-25)' in docs
    assert 'Section helper descriptions should remain at or below 72 characters' in docs
    assert '50/50' in docs
    assert 'stack the blocks vertically' in docs
    assert 'Paired sections reserve 5.6mm of clearance' in docs


def test_family_pairs_reserve_bottom_clearance_and_align_descriptions() -> None:
    css = read('app/static/reports/pdf/analytics_publication.css')
    compact = ''.join(css.split())
    assert '--analytics-rhythm-pair-clearance:5.6mm' in compact
    assert 'padding-bottom:var(--analytics-rhythm-pair-clearance)' in compact
    assert '.page-content>.two-column' in compact
    assert 'margin-top:var(--analytics-rhythm-section)' in compact
    assert '.two-column>.content-section>.section-subtitle' in compact
    assert 'min-height:5.2mm' in compact


def test_workload_half_width_signal_register_uses_compact_labels() -> None:
    presenter = read('app/reports/export/html_pdf/workload_analysis.py')
    assert "'Missing ResourceQuota'" in presenter
    assert "'Incomplete Requests'" in presenter
    assert "'Memory Limit Review'" in presenter


def test_storage_trend_avoids_start_and_cutoff_label_collision() -> None:
    presenter = read('app/reports/export/html_pdf/storage_analysis.py')
    assert 'compact_axis_labels = cutoff_x - left < 70' in presenter
    assert "if not compact_axis_labels" in presenter


def test_resource_utilization_interpretation_sections_render_body_copy() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')
    assert '<p>{{ p.pod_node.interpretation }}</p>' in template
    assert '<p>{{ p.trend.interpretation }}</p>' in template

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = PROJECT_ROOT / 'app' / 'templates' / 'reports' / 'pdf'
CSS_DIR = PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf'
HTML_PDF_DIR = PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf'

ANALYTICS_TEMPLATES = (
    'analytics_overview.html',
    'resource_utilization.html',
    'capacity_analysis.html',
    'storage_analysis.html',
    'workload_analysis.html',
    'forecast_analysis.html',
    'top_consumers_analysis.html',
    'alerts_anomalies.html',
)

ANALYTICS_PRESENTATION_MODULES = (
    'analytics_overview.py',
    'resource_utilization.py',
    'capacity_analysis.py',
    'storage_analysis.py',
    'workload_analysis.py',
    'forecast_analysis.py',
    'top_consumers_analysis.py',
    'alerts_anomalies.py',
)


def test_analytics_publication_component_contract_is_parseable() -> None:
    component = TEMPLATE_DIR / 'components' / 'analytics_publication.html'
    source = component.read_text(encoding='utf-8')
    Environment().parse(source)

    for macro in (
        'status_label',
        'report_header',
        'page_title',
        'footer',
        'cover_brand',
        'cover_title',
        'cover_contents',
        'methodology_register',
        'metric_strip',
        'section',
        'technical_table',
        'findings_table',
        'recommendation_table',
        'interpretation_card',
        'reference_item',
        'reference_register',
        'evidence_boundary',
        'status_language',
        'identity_register',
    ):
        assert f'macro {macro}' in source


def test_all_analytics_templates_use_the_isolated_analytics_contract() -> None:
    for filename in ANALYTICS_TEMPLATES:
        source = (TEMPLATE_DIR / filename).read_text(encoding='utf-8')
        Environment().parse(source)
        assert 'kaori-analytics-publication' in source, filename
        assert "import 'reports/pdf/components/analytics_publication.html' as ui" in source, filename
        assert 'kaori-publication-standard' not in source, filename
        assert 'ui.report_header' in source, filename
        assert 'ui.page_title' in source, filename
        assert 'ui.footer' in source, filename
        assert 'ui.metric_strip' in source, filename
        assert 'ui.section' in source, filename
        assert 'ui.cover_brand' in source, filename
        assert 'ui.cover_title' in source, filename
        assert 'ui.cover_contents' in source, filename


def test_analytics_css_owns_the_canonical_visual_and_table_contract() -> None:
    css = (CSS_DIR / 'analytics_publication.css').read_text(encoding='utf-8')
    compact = css.replace(' ', '')

    assert 'KAORI Analytics PDF Publication Standard v3.0' in css
    assert '--analytics-primary:#7C3AED' in compact
    assert '--analytics-primary-dark:#4C1D95' in compact
    assert '@page{size:A4portrait;margin:0;}' in compact
    assert 'height:297mm' in compact
    assert '.report-header' in css
    assert '.page-title-row' in css
    assert '.metric-strip' in css
    assert '.section-rule' in css and 'display:none' in compact
    assert '.cover-masthead' in css
    assert '.cover-contents' in css
    assert 'width:100%' in compact
    assert '.reference-notes' in css
    assert '.methodology-grid' in css
    assert '.boundary-columns' in css
    assert '.limitations-grid' in css
    assert '.status-language-grid' in css
    assert 'vertical-align:middle' in compact
    assert 'table-layout:fixed' in compact
    assert 'text-overflow:ellipsis' not in compact


def test_report_specific_analytics_css_contains_only_specialization() -> None:
    forbidden_exact_selectors = (
        '.report-header',
        '.page-title-row',
        '.page-footer',
        '.metric-strip',
        '.content-section',
        '.section-rule',
        '.report-table',
        '.cover-band',
    )
    exact_rule = re.compile(r'^\s*([^@/][^{]+)\{', re.MULTILINE)

    for template in ANALYTICS_TEMPLATES:
        css_path = CSS_DIR / template.replace('.html', '.css')
        css = css_path.read_text(encoding='utf-8')
        assert 'specialization v3.0' in css or 'PDF specialization v3.0' in css
        assert '@font-face' not in css, css_path.name
        assert '@page' not in css, css_path.name
        selectors = {match.group(1).strip() for match in exact_rule.finditer(css)}
        for selector in forbidden_exact_selectors:
            assert selector not in selectors, f'{selector} redefined in {css_path.name}'


def test_engine_loads_analytics_standard_after_report_specialization() -> None:
    source = (HTML_PDF_DIR / 'engine.py').read_text(encoding='utf-8')
    assert 'ANALYTICS_TEMPLATE_STYLESHEETS' in source
    assert 'ANALYTICS_SHARED_STYLESHEET' in source
    assert 'analytics_stylesheet = ANALYTICS_TEMPLATE_STYLESHEETS.get(document.template_name)' in source
    assert 'analytics_css_path = css_path.with_name(ANALYTICS_SHARED_STYLESHEET)' in source
    assert source.index('CSS(filename=str(report_css_path)') < source.index('CSS(filename=str(analytics_css_path)')


def test_all_analytics_presentations_declare_the_canonical_reference() -> None:
    for filename in ANALYTICS_PRESENTATION_MODULES:
        source = (HTML_PDF_DIR / filename).read_text(encoding='utf-8')
        assert 'ANALYTICS_PUBLICATION_FAMILY' in source, filename
        assert 'ANALYTICS_PUBLICATION_STANDARD' in source, filename
        assert 'ANALYTICS_CANONICAL_REFERENCE' in source, filename
        assert 'analytics_layout_contract' in source, filename
        assert "'publication_family': ANALYTICS_PUBLICATION_FAMILY" in source, filename
        assert "'publication_standard': ANALYTICS_PUBLICATION_STANDARD" in source, filename
        assert "'canonical_reference': ANALYTICS_CANONICAL_REFERENCE" in source, filename
        assert "'layout_contract': analytics_layout_contract(" in source, filename


def test_analytics_standard_centralizes_shared_layout_policy() -> None:
    source = (HTML_PDF_DIR / 'analytics_publication_standard.py').read_text(encoding='utf-8')

    assert "ANALYTICS_PUBLICATION_STANDARD = 'kaori-analytics-pdf-v3.0'" in source
    assert "ANALYTICS_VISUAL_STYLE = 'kaori-publication-v3-neutral-evidence-first'" in source
    assert 'def analytics_layout_contract(' in source
    for value in (
        "'cover_header_policy': 'symmetric-two-sided'",
        "'section_separator_policy': 'none'",
        "'section_rhythm': 'title-subtitle-content'",
        "'table_alignment': 'left-middle'",
        "'methodology_layout': 'parallel-registers'",
    ):
        assert value in source

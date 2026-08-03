from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = PROJECT_ROOT / 'app' / 'templates' / 'reports' / 'pdf'
CSS_DIR = PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf'

STANDARD_TEMPLATES = (
    'tls_certificate_health.html',
    'inventory_publication_base.html',
)


def test_shared_publication_component_contract_is_parseable() -> None:
    component = TEMPLATE_DIR / 'components' / 'kaori_publication.html'
    source = component.read_text(encoding='utf-8')
    Environment().parse(source)

    for macro in (
        'report_header',
        'page_title',
        'footer',
        'metric_strip',
        'section',
        'technical_table',
        'recommendation_table',
        'interpretation_card',
        'reference_item',
    ):
        assert f'macro {macro}' in source


def test_all_fixed_publications_delegate_common_markup_to_shared_component() -> None:
    for filename in STANDARD_TEMPLATES:
        source = (TEMPLATE_DIR / filename).read_text(encoding='utf-8')
        assert 'kaori-publication-standard' in source, filename
        assert "import 'reports/pdf/components/kaori_publication.html' as ui" in source, filename
        assert 'ui.report_header' in source, filename
        assert 'ui.page_title' in source, filename
        assert 'ui.footer' in source, filename
        assert 'ui.metric_strip' in source, filename
        assert 'ui.section' in source, filename


def test_shared_css_defines_the_kaori_publication_design_tokens() -> None:
    css = (CSS_DIR / 'kaori_publication.css').read_text(encoding='utf-8')

    assert '--kaori-primary: #7C3AED' in css
    assert '--kaori-primary-dark: #4C1D95' in css
    assert '--kaori-primary-soft: #EDE9FE' in css
    assert '.section-rule > span' in css
    assert 'width: 25mm' in css
    assert '.interpretation-card.warning-card' in css
    assert '.methodology-grid' in css
    assert '.boundary-columns' in css
    assert '.reference-notes' in css


def test_inventory_css_contains_only_inventory_specialization() -> None:
    css = (CSS_DIR / 'inventory_publications.css').read_text(encoding='utf-8')

    assert 'Inventory-specific layout on top of kaori_publication.css' in css
    assert '@font-face' not in css
    assert '@page' not in css
    assert '.report-header {' not in css
    assert '.page-title-row {' not in css
    assert '.section-rule {' not in css

from pathlib import Path

from jinja2 import Environment


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = PROJECT_ROOT / 'app' / 'templates' / 'reports' / 'pdf'
HTML_PDF_DIR = PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf'
CSS_DIR = PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf'

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

ANALYTICS_BUILDERS = (
    'analytics_overview.py',
    'resource_utilization.py',
    'capacity_analysis.py',
    'storage_analysis.py',
    'workload_analysis.py',
    'forecast_analysis.py',
    'top_consumers_analysis.py',
    'alerts_anomalies.py',
)


def test_all_analytics_templates_use_shared_publication_primitives() -> None:
    environment = Environment()

    for filename in ANALYTICS_TEMPLATES:
        source = (TEMPLATE_DIR / filename).read_text(encoding='utf-8')
        environment.parse(source)

        assert "components/analytics_publication.html" in source, filename
        assert 'ui.cover_brand(' in source, filename
        assert 'ui.cover_title(' in source, filename
        assert 'ui.cover_contents(' in source, filename
        assert 'report_header()' in source, filename
        assert 'page_title(' in source, filename
        assert 'footer(' in source, filename
        assert 'ui.section(' in source, filename
        assert 'Methodology' in source, filename
        assert 'Evidence Boundary' in source, filename


def test_all_analytics_builders_declare_the_same_layout_contract() -> None:
    for filename in ANALYTICS_BUILDERS:
        source = (HTML_PDF_DIR / filename).read_text(encoding='utf-8')

        assert 'ANALYTICS_PUBLICATION_FAMILY' in source, filename
        assert 'ANALYTICS_PUBLICATION_STANDARD' in source, filename
        assert 'ANALYTICS_CANONICAL_REFERENCE' in source, filename
        assert 'analytics_layout_contract' in source, filename
        assert "'publication_family': ANALYTICS_PUBLICATION_FAMILY" in source, filename
        assert "'publication_standard': ANALYTICS_PUBLICATION_STANDARD" in source, filename
        assert "'canonical_reference': ANALYTICS_CANONICAL_REFERENCE" in source, filename


def test_shared_css_owns_the_new_analytics_visual_contract() -> None:
    source = (CSS_DIR / 'analytics_publication.css').read_text(encoding='utf-8')
    compact = ''.join(source.split())

    assert 'KAORIAnalyticsPDFPublicationStandardv1.1' in compact
    assert '.cover-masthead' in source
    assert '.cover-contents' in source
    assert '.section-rule { display: none; }' in source
    assert 'vertical-align: middle' in source
    assert '.methodology-grid' in source
    assert '.boundary-columns' in source
    assert '.limitations-grid' in source
    assert '.status-language-grid' in source


def test_standard_registry_covers_all_analytics_templates() -> None:
    source = (HTML_PDF_DIR / 'analytics_publication_standard.py').read_text(encoding='utf-8')

    assert "ANALYTICS_PUBLICATION_STANDARD = 'kaori-analytics-pdf-v1.1'" in source
    assert "ANALYTICS_VISUAL_STYLE = 'reporting-standard-v2.9.2-analytics-family'" in source
    assert "'cover_header_policy': 'symmetric-two-sided'" in source
    assert "'section_separator_policy': 'none'" in source
    assert "'section_rhythm': 'title-subtitle-content'" in source
    assert "'table_alignment': 'left-middle'" in source
    assert "'methodology_layout': 'parallel-registers'" in source

    for filename in ANALYTICS_TEMPLATES:
        assert f"'reports/pdf/{filename}'" in source, filename

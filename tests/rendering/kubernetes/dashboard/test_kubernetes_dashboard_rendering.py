from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[4]
DASHBOARD_TEMPLATES = ROOT / 'app/templates/kubernetes/dashboard'


def test_all_kubernetes_dashboard_templates_parse_as_valid_jinja() -> None:
    environment = Environment(autoescape=True)

    templates = sorted(DASHBOARD_TEMPLATES.rglob('*.html'))
    assert templates
    for template in templates:
        environment.parse(template.read_text(encoding='utf-8'))


def test_dashboard_uses_canonical_hero_tabs_table_status_and_pagination_components() -> None:
    hero = (DASHBOARD_TEMPLATES / 'partials/_hero.html').read_text(encoding='utf-8')
    page_hero = (ROOT / 'app/templates/components/page_hero.html').read_text(encoding='utf-8')
    content = (DASHBOARD_TEMPLATES / 'partials/_content.html').read_text(encoding='utf-8')
    cluster_health = (DASHBOARD_TEMPLATES / 'partials/_cluster_health.html').read_text(encoding='utf-8')

    assert 'components/page_hero.html' in hero
    assert 'page_hero.operational_dashboard(' in hero
    assert "context_header('Dashboard Context', 'Operational Signal Scope', 'scan-search')" in page_hero
    assert 'components/workspace_tabs.html' in content
    assert 'components/table.html' in cluster_health
    assert 'components/table_label.html' in cluster_health
    assert 'components/pagination.html' in cluster_health
    assert '[5, 10, 25, 50]' in cluster_health

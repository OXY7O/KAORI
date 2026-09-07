from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _word_count(value: str) -> int:
    return len(value.replace('–', ' ').split())


def test_dynamic_jinja_hero_descriptions_are_discovered_and_budgeted() -> None:
    namespace = runpy.run_path(str(ROOT / 'scripts' / 'verify_hero_component_standard.py'))
    collector = namespace['_literal_hero_descriptions']
    account_hero = ROOT / 'app' / 'templates' / 'settings' / 'account' / 'partials' / '_hero.html'

    descriptions = collector([account_hero])

    assert len(descriptions) == 3
    assert all(11 <= _word_count(description) <= 19 for description in descriptions.values())


def test_generic_blocked_analytics_hero_preserves_operational_metadata() -> None:
    blocked = (ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'materialization' / 'blocked.html').read_text(
        encoding='utf-8'
    )
    presentation = (ROOT / 'app' / 'kubernetes' / 'analytics' / 'materialization' / 'presentation.py').read_text(
        encoding='utf-8'
    )

    assert 'page_hero.analytics_metadata(' in blocked
    assert 'materialization_metadata' in presentation
    assert "'No Cluster Selected'" in presentation
    assert "'Blocked Readiness'" in presentation


def test_capacity_and_utilization_blocked_routes_share_the_metadata_safe_renderer() -> None:
    routes = (
        ROOT / 'app' / 'kubernetes' / 'analytics' / 'capacity' / 'routes.py',
        ROOT / 'app' / 'kubernetes' / 'analytics' / 'utilization' / 'routes.py',
    )
    for route in routes:
        source = route.read_text(encoding='utf-8')
        assert 'blocked_page_context' in source, route
        assert 'kubernetes/analytics/materialization/blocked.html' in source, route

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ANALYTICS = ROOT / 'app/templates/analytics'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_analytics_final_lock_v2_uses_precise_record_detail_actions() -> None:
    templates = '\n'.join(path.read_text(encoding='utf-8') for path in ANALYTICS.rglob('*.html'))
    assert 'View More' not in templates
    for relative in (
        'app/templates/analytics/alerts/partials/_alerts_table_row.html',
        'app/templates/analytics/alerts/partials/_anomalies_table_row.html',
        'app/templates/analytics/workload/partials/_tenant_quota_section.html',
        'app/templates/analytics/workload/partials/_workload_mapping_section.html',
        'app/templates/analytics/top_consumers/partials/_consumer_detail_results.html',
    ):
        assert 'View Details' in read(relative)


def test_forecast_hero_uses_dedicated_canonical_partial() -> None:
    index = read('app/templates/analytics/forecast/index.html')
    hero = read('app/templates/analytics/forecast/partials/_hero.html')

    assert '{% include "analytics/forecast/partials/_hero.html" %}' in index
    assert 'page_hero.shell_classes()' not in index
    assert 'components/page_hero.html' in hero
    assert 'page_hero.shell_classes()' in hero
    assert 'All Namespaces' in hero
    assert "url_for('integrations.kubernetes')" in hero


def test_top_consumer_summary_never_fakes_missing_committed_evidence() -> None:
    summary = read('app/templates/analytics/top_consumers/partials/_summary.html')
    assert 'card.value|default("N/A", true)' in summary
    assert "identity.entity_label|default('No Evidence', true)" in summary
    assert "identity.primary|default('No Evidence', true)" in summary


def test_all_analytics_top_level_pages_keep_dependency_guardrails() -> None:
    for relative in (
        'app/templates/analytics/overview/index.html',
        'app/templates/analytics/utilization/index.html',
        'app/templates/analytics/capacity/index.html',
        'app/templates/analytics/storage/index.html',
        'app/templates/analytics/workload/index.html',
        'app/templates/analytics/forecast/index.html',
        'app/templates/analytics/top_consumers/index.html',
        'app/templates/analytics/alerts/index.html',
    ):
        source = read(relative)
        assert 'kaori-analytics-page' in source
        assert 'dependency_blocker' in source


def test_analytics_final_lock_verifier_is_v2() -> None:
    verifier = read('scripts/verify_analytics_final_lock.py')
    readme = read('app/analytics/README.md')
    assert 'KAORI Kubernetes Analytics Final Lock v2' in verifier
    assert "'View More' not in combined_templates" in verifier
    assert 'Final Lock v2' in readme

from pathlib import Path


OVERVIEW_ROOT = Path('app/templates/analytics/overview')


def test_overview_controls_and_readiness_share_one_compact_box() -> None:
    source = (OVERVIEW_ROOT / 'partials/_health_summary.html').read_text()
    hero = (OVERVIEW_ROOT / 'partials/_hero.html').read_text()

    assert 'Analytics Controls &amp; Data Readiness' in source
    assert 'id="analytics-overview-filter"' in source
    assert 'h-9 min-w-0 flex-1' in source
    assert 'prometheus_status_panel.render' in source
    assert 'compact=true, flat=true' in source
    assert 'Latest Analytics Data Snapshot' in source
    assert 'Latest Sync' in source
    assert 'Coverage' in source
    assert 'Committed data currently used by this overview.' not in source
    assert "payload.selected_cluster.name|default('Selected Cluster')" not in source
    assert 'id="analytics-overview-filter"' not in hero


def test_prometheus_compact_mode_avoids_nested_card_and_connected_message() -> None:
    source = Path('app/templates/analytics/components/_prometheus_status.html').read_text()

    assert 'flat=false' in source
    assert '{% if flat %}min-w-0' in source
    assert '{% if not connected or not compact %}' in source


def test_operational_health_summary_is_a_separate_box() -> None:
    source = (OVERVIEW_ROOT / 'partials/_health_summary.html').read_text()

    assert source.count('<section class="overflow-hidden rounded-xl') == 2
    assert 'Operational Health Summary' in source
    assert '6 Health Signals' in source
    index_source = (OVERVIEW_ROOT / 'index.html').read_text()
    assert 'id="overview-health-summary"' in index_source
    assert 'class="space-y-6"' in index_source


def test_overview_tabs_and_content_share_one_workspace_box() -> None:
    source = (OVERVIEW_ROOT / 'index.html').read_text()

    assert 'id="analytics-overview-workspace"' in source
    assert "embedded=true" in source
    assert 'class="p-4 sm:p-5"' in source


def test_overview_recommendations_are_always_visible() -> None:
    for filename in (
        'partials/_actionable_recommendation_summary.html',
        'partials/_recommendations.html',
    ):
        source = (OVERVIEW_ROOT / filename).read_text()
        assert '<details' not in source
        assert '<summary' not in source
        assert 'group-open:' not in source

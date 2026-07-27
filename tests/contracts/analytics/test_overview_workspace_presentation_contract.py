from pathlib import Path


OVERVIEW_ROOT = Path('app/templates/analytics/overview')


def test_overview_health_combines_prometheus_and_snapshot_readiness() -> None:
    source = (OVERVIEW_ROOT / 'partials/_health_summary.html').read_text()

    assert 'Analytics Health &amp; Data Readiness' in source
    assert 'prometheus_status_panel.render' in source
    assert 'Latest Analytics Data Snapshot' in source
    assert 'Latest Data Sync' in source
    assert 'Snapshot Coverage' in source


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

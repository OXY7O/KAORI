from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_top_consumers_panels_have_native_hidden_fallback():
    template = read("app/templates/analytics/top_consumers/partials/_top_consumers_section.html")
    assert "data-top-consumers-tabset" in template
    assert "x-bind:hidden=\"activeTab !== 'overview'\"" in template
    assert "x-bind:hidden=\"activeTab !== 'detail'\"" in template
    assert "x-bind:hidden=\"activeTab !== 'recommendations'\"" in template
    assert template.count("\n             hidden\n             x-cloak") >= 2


def test_cluster_filter_uses_single_htmx_replacement_boundary():
    template = read("app/templates/analytics/top_consumers/partials/_controls_readiness.html")
    assert 'hx-sync="#top-consumers-page:replace"' in template
    assert 'hx-target="#top-consumers-page"' in template
    assert 'hx-select="#top-consumers-page"' in template


def test_consumer_detail_has_local_standard_loading_bar():
    template = read("app/templates/analytics/top_consumers/partials/_consumer_detail_section.html")
    pagination = read("app/templates/analytics/top_consumers/partials/_consumer_detail_pagination.html")
    assert '{% import "components/loading_bar.html" as loading_bar %}' in template
    assert "loading_bar.render('consumer-detail-loading-indicator'" in template
    assert 'hx-indicator="#consumer-detail-loading-indicator"' in template
    assert 'hx-sync="#consumer-detail-results:replace"' in template
    assert 'hx-target="#consumer-detail-results"' in template
    assert 'hx-indicator="#consumer-detail-loading-indicator"' in pagination
    assert "top-consumers-refresh-indicator" not in pagination


def test_top_consumers_is_rehydrated_after_htmx_swap():
    script = read("app/static/js/analytics_controls.js")
    section = read("app/templates/analytics/top_consumers/partials/_top_consumers_section.html")
    assert "function stabilizeAnalyticsTabsets(root)" in script
    assert "window.Alpine.initTree(tabset)" in script
    assert "stabilizeAnalyticsTabsets(root)" in script
    assert "data-analytics-tabset" in section

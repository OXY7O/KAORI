from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_top_consumer_freshness_is_embedded_in_controls_workspace():
    index = read("app/templates/analytics/top_consumers/index.html")
    controls = read(
        "app/templates/analytics/top_consumers/partials/_controls_readiness.html"
    )

    assert 'analytics/materialization/_freshness.html' not in index
    assert "Last Successful Snapshot" in controls
    assert "Readiness Evidence Incomplete" in controls
    assert "Latest Refresh Error" in controls
    assert "source_warning" in controls
    assert "last_error" in controls


def test_consumer_detail_uses_persistent_kaori_loading_bar_and_results_swap():
    section = read(
        "app/templates/analytics/top_consumers/partials/_consumer_detail_section.html"
    )
    results = read(
        "app/templates/analytics/top_consumers/partials/_consumer_detail_results.html"
    )
    pagination = read(
        "app/templates/analytics/top_consumers/partials/_consumer_detail_pagination.html"
    )
    routes = read("app/analytics/top_consumers/routes.py")

    assert "loading_bar.render('consumer-detail-loading-indicator'" in section
    assert 'hx-target="#consumer-detail-results"' in section
    assert 'hx-sync="#consumer-detail-results:replace"' in section
    assert 'id="consumer-detail-results"' in results
    assert 'hx-target="#consumer-detail-results"' in results
    assert 'hx-target="#consumer-detail-results"' in pagination
    assert 'hx-indicator="#consumer-detail-loading-indicator"' in pagination
    assert 'hx-sync="#consumer-detail-results:replace"' in pagination
    assert "_consumer_detail_results.html" in routes
    assert "_consumer_detail_section.html', **(context or {})" not in routes


def test_analytics_tabs_do_not_write_hash_or_move_viewport():
    script = read("app/static/js/analytics_controls.js")

    assert "window.sessionStorage.setItem(analyticsTabStorageKey(tabsetId), tabId)" in script
    assert "url.hash = tab" not in script
    assert "Hash updates can move the viewport" in script
    assert "url.hash = ''" in script
    assert "function stabilizeAlertsAfterSwap(root)" in script
    assert "function stabilizeTopConsumersAfterSwap(root)" in script

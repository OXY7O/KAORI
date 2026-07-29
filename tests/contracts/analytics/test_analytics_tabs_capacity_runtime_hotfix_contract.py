from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_capacity_allocation_uses_explicit_mapping_keys() -> None:
    template = read("app/templates/analytics/capacity/partials/_allocation.html")

    assert "section.items" not in template
    assert "section['items']|default([], true)" in template
    assert "section['title']" in template
    assert "section_status['label']" in template
    assert "allocation_item['percent']" in template


def test_shared_tabs_have_native_controller_contract() -> None:
    workspace = read("app/templates/analytics/components/_analysis_workspace.html")
    tabs = read("app/templates/analytics/components/_content_tabs.html")
    controls = read("app/static/js/analytics_controls.js")

    assert 'data-analytics-tabset-id="{{ tabset_id }}"' in workspace
    assert "tabset_id|tojson" in workspace
    assert 'data-analytics-tab-button="{{ tab_id }}"' in tabs
    assert "function setAnalyticsTab(tabset, tabId" in controls
    assert "event.target.closest?.('[data-analytics-tab-button]')" in controls
    assert "panel.hidden = panel.dataset.analyticsTabPanel !== tabId" in controls
    assert "focus({ preventScroll: true })" in controls
    assert "analyticsTabStorageKey(tabsetId)" in controls


def test_target_analytics_pages_expose_native_tab_panels() -> None:
    targets = {
        "app/templates/analytics/capacity/index.html": (
            "summary",
            "allocation",
            "risk",
            "recommendations",
        ),
        "app/templates/analytics/storage/partials/_storage_section.html": (
            "capacity",
            "filesystem",
            "pvc",
            "pv",
            "recommendations",
        ),
        "app/templates/analytics/workload/index.html": (
            "quotas",
            "mapping",
            "recommendations",
        ),
        "app/templates/analytics/utilization/index.html": (
            "summary",
            "trend",
            "nodes",
            "recommendations",
        ),
    }

    for relative, panels in targets.items():
        template = read(relative)
        for panel in panels:
            assert f'data-analytics-tab-panel="{panel}"' in template
            assert f'x-bind:hidden="activeTab !== \'{panel}\'"' in template


def test_non_default_panels_have_native_hidden_fallback() -> None:
    for relative in (
        "app/templates/analytics/capacity/index.html",
        "app/templates/analytics/storage/partials/_storage_section.html",
        "app/templates/analytics/workload/index.html",
        "app/templates/analytics/utilization/index.html",
    ):
        template = read(relative)
        assert "hidden x-cloak" in template or "hidden\n                         x-cloak" in template


def test_utilization_tabset_uses_shared_runtime_boundary() -> None:
    template = read("app/templates/analytics/utilization/index.html")

    assert "data-analytics-tabset" in template
    assert 'data-analytics-tabset-id="utilization-content"' in template
    assert 'data-default-tab="summary"' in template
    assert 'kaoriAnalyticsTabs("summary"' in template

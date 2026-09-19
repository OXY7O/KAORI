from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_analytics_tabs_have_one_native_runtime_owner() -> None:
    runtime = read('app/static/js/analytics/controls.js')
    templates = '\n'.join(
        path.read_text(encoding='utf-8') for path in (ROOT / 'app/templates/analytics').rglob('*.html')
    )

    assert 'function setAnalyticsTab(tabset, tabId' in runtime
    assert "event.target.closest?.('[data-analytics-tab-button]')" in runtime
    assert 'panel.hidden = panel.dataset.analyticsTabPanel !== tabId' in runtime
    assert "url.searchParams.set('tab', tabId)" in runtime
    assert "window.history.replaceState({}, '', url)" in runtime
    assert "window.htmx.trigger(target, 'kaori:analytics-tab-activated')" in runtime
    assert 'data-kaori-tab-active-classes' in read('app/templates/components/content_tabs.html')
    assert 'data-kaori-tab-inactive-classes' in read('app/templates/components/content_tabs.html')
    assert "tabStateClasses(button, 'active')" in runtime
    assert 'ANALYTICS_TAB_ACTIVE_CLASSES' not in runtime
    assert 'stabilizeAlertsAfterSwap' not in runtime
    assert 'data-alerts-tabset' not in runtime
    assert 'kaoriAnalyticsTabs' not in runtime
    assert 'const alpineState = tabset._x_dataStack' not in runtime
    assert 'const alpineTab = tabset._x_dataStack' not in runtime
    assert 'x-show="activeTab' not in templates
    assert 'x-bind:hidden="activeTab' not in templates


def test_overview_tabs_are_compact_one_row_without_internal_snapshot_badges() -> None:
    overview = read('app/templates/kubernetes/analytics/overview/index.html')
    shared = read('app/templates/components/content_tabs.html')

    assert "('utilization', 'Usage'" in overview
    assert "('workloads', 'Workload'" in overview
    assert "('action-summary', 'Actions'" in overview
    assert "('recommendations', 'Guidance'" in overview
    assert 'show_badges=false' in overview
    assert 'nowrap=true' in overview
    assert "'min-w-max flex-nowrap' if nowrap else 'flex-wrap'" in shared
    assert "'overflow-x-auto ' if nowrap else ''" in shared
    assert 'resource-snapshot' in overview
    assert 'data-overview-section-label="{{ tab[1] }}"' in overview


def test_analytics_consumes_shared_content_tabs_without_compatibility_wrapper() -> None:
    workspace = read('app/templates/kubernetes/analytics/components/_analysis_workspace.html')
    overview = read('app/templates/kubernetes/analytics/overview/index.html')
    consumers = read('app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html')

    for source in (workspace, overview, consumers):
        assert 'components/content_tabs.html' in source
        assert 'content_tabs.render_buttons' in source
    assert not (ROOT / 'app/templates/analytics/components/_content_tabs.html').exists()
    assert not (ROOT / 'app/templates/analytics/components/_snapshot_panel.html').exists()
    assert not (ROOT / 'app/templates/kubernetes/analytics/materialization/_freshness.html').exists()


def test_analytics_final_recheck_evidence_is_wired_to_release_gate() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    tracker = read('docs/reviews/2026-08-10-final-recheck.md')

    assert 'python scripts/verify_analytics_final_lock.py' in quality_gate
    assert 'tests/kubernetes/analytics' in quality_gate
    assert 'test_analytics_final_release_contract.py' in coverage
    assert 'test_analytics_security.py' in coverage
    assert 'test_analytics_rendering.py' in coverage
    assert '06 — Kubernetes Analytics' in tracker


def test_materialized_snapshot_and_forecast_read_paths_have_no_runtime_compatibility_fallback() -> None:
    serialization = read('app/kubernetes/analytics/materialization/serialization.py')
    forecast = read('app/kubernetes/analytics/forecast/presentation.py')

    assert 'load_cluster_reference' not in serialization
    assert 'Backward compatibility' not in serialization
    assert '_FORECAST_LEGACY_KEYS' not in forecast
    assert 'for legacy_key in' not in forecast


def test_content_tabs_are_registered_as_a_shared_kaori_tab_style() -> None:
    registry = read('docs/design/components/TAB_STYLES.md')
    standard = read('docs/design/components/CONTENT_TABS.md')
    design_readme = read('docs/design/README.md')

    assert 'Tab Style 4 — Content Tabs' in registry
    assert 'components/content_tabs.html' in standard
    assert 'data-kaori-tab-active-classes' in standard
    assert 'resource-snapshot' in standard
    assert 'must never be rendered' in standard
    assert 'components/CONTENT_TABS.md' in design_readme

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_capacity_allocation_uses_explicit_mapping_keys() -> None:
    template = read('app/templates/analytics/kubernetes/capacity/partials/_allocation.html')

    assert 'section.items' not in template
    assert "section['items']|default([], true)" in template
    assert "section['title']" in template
    assert "section_status['label']" in template
    assert "allocation_item['percent']" in template


def test_shared_tabs_have_native_controller_contract() -> None:
    workspace = read('app/templates/analytics/kubernetes/components/_analysis_workspace.html')
    tabs = read('app/templates/components/content_tabs.html')
    controls = read('app/static/js/analytics/controls.js')

    assert 'data-analytics-tabset-id="{{ tabset_id }}"' in workspace
    assert 'data-default-tab="{{ initial_tab }}"' in workspace
    assert 'kaoriAnalyticsTabs' not in workspace
    assert 'data-{{ data_namespace }}-tab-button="{{ tab_id }}"' in tabs
    assert 'function setAnalyticsTab(tabset, tabId' in controls
    assert "event.target.closest?.('[data-analytics-tab-button]')" in controls
    assert 'panel.hidden = panel.dataset.analyticsTabPanel !== tabId' in controls
    assert 'focus({ preventScroll: true })' in controls
    assert 'analyticsTabStorageKey(tabsetId)' in controls


def test_target_analytics_pages_expose_native_tab_panels() -> None:
    targets = {
        'app/templates/analytics/kubernetes/capacity/index.html': (
            'summary',
            'allocation',
            'risk',
            'recommendations',
        ),
        'app/templates/analytics/kubernetes/storage/partials/_storage_section.html': (
            'capacity',
            'filesystem',
            'pvc',
            'pv',
            'recommendations',
        ),
        'app/templates/analytics/kubernetes/workload/index.html': (
            'quotas',
            'mapping',
            'recommendations',
        ),
        'app/templates/analytics/kubernetes/utilization/index.html': (
            'summary',
            'trend',
            'nodes',
            'recommendations',
        ),
    }

    for relative, panels in targets.items():
        template = read(relative)
        for panel in panels:
            assert f'data-analytics-tab-panel="{panel}"' in template

    combined = '\n'.join(read(relative) for relative in targets)
    assert 'x-show="activeTab' not in combined
    assert 'x-bind:hidden="activeTab' not in combined


def test_non_default_panels_have_native_hidden_fallback() -> None:
    for relative in (
        'app/templates/analytics/kubernetes/capacity/index.html',
        'app/templates/analytics/kubernetes/storage/partials/_storage_section.html',
        'app/templates/analytics/kubernetes/workload/index.html',
        'app/templates/analytics/kubernetes/utilization/index.html',
    ):
        template = read(relative)
        assert 'hidden' in template
        assert 'x-cloak' not in template


def test_utilization_tabset_uses_shared_runtime_boundary() -> None:
    template = read('app/templates/analytics/kubernetes/utilization/index.html')
    shared = read('app/templates/analytics/kubernetes/components/_analysis_workspace.html')

    assert 'analytics_workspace.tabbed(' in template
    assert "'utilization-content'" in template
    assert "'summary'" in template
    assert 'data-analytics-tabset' in shared
    assert 'data-analytics-tabset-id="{{ tabset_id }}"' in shared
    assert 'data-default-tab="{{ initial_tab }}"' in shared
    assert 'kaoriAnalyticsTabs' not in shared
    assert 'content_tabs.render_buttons' in shared

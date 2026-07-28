from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[3]
ALERTS = ROOT / 'app/templates/analytics/alerts'
STATIC_JS = ROOT / 'app/static/js'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_cluster_and_fragment_requests_share_one_htmx_sync_boundary() -> None:
    index = _read(ALERTS / 'index.html')
    pagination = _read(ALERTS / 'partials/_pagination.html')
    pagination_js = _read(STATIC_JS / 'pagination.js')

    assert 'hx-sync="#alerts-page-content:replace"' in index
    assert pagination.count('hx-sync="{{ target_id }}:replace"') >= 3
    assert "'hx-sync'" in pagination_js


def test_alert_swap_targets_are_explicit_hydration_boundaries() -> None:
    index = _read(ALERTS / 'index.html')
    alerts_table = _read(ALERTS / 'partials/_alerts_table.html')
    anomalies_table = _read(ALERTS / 'partials/_anomalies_table.html')

    assert 'id="alerts-page-content"' in index
    assert 'data-alerts-swap-boundary' in index
    assert 'id="alerts-table-container" data-alerts-swap-boundary' in alerts_table
    assert 'id="anomalies-table-container" data-alerts-swap-boundary' in anomalies_table


def test_tab_panels_have_native_hidden_fallback_after_full_page_swap() -> None:
    index = _read(ALERTS / 'index.html')

    for tab in ('alerts', 'anomalies', 'routing', 'ownership', 'recommendations'):
        assert f'data-alerts-tab-panel="{tab}"' in index
        assert f'x-bind:hidden="activeTab !== \'{tab}\'"' in index

    # Alerts is the server-rendered default. Every other panel is natively hidden
    # until Alpine restores the persisted tab.
    assert index.count('\n                         hidden\n                         x-cloak') >= 4


def test_record_details_remain_closed_without_alpine_hydration() -> None:
    alert_row = _read(ALERTS / 'partials/_alerts_table_row.html')
    anomaly_row = _read(ALERTS / 'partials/_anomalies_table_row.html')
    anomaly_table = _read(ALERTS / 'partials/_anomalies_table.html')

    assert 'x-bind:hidden="!expanded"' in alert_row
    assert '\n         hidden\n         x-cloak' in alert_row
    assert 'x-bind:hidden="!expanded"' in anomaly_row
    assert '@kaori:alerts-collapse.window="expanded = false"' in anomaly_row
    assert 'id="anomalies-table-container"' in anomaly_table


def test_alert_hydration_uses_connected_swap_target_and_reconciles_one_panel() -> None:
    script = _read(STATIC_JS / 'analytics_controls.js')

    assert 'candidate.isConnected' in script
    assert 'function stabilizeAlertsAfterSwap(root)' in script
    assert 'function stabilizeAnalyticsTabsets(root)' in script
    assert "panel.hidden = panel.dataset.analyticsTabPanel !== tabId" in script
    assert "htmx:afterSwap" in script
    assert "htmx:afterSettle" in script


def test_changed_alert_templates_parse() -> None:
    environment = Environment()
    for relative in (
        'index.html',
        'partials/_alerts_table.html',
        'partials/_alerts_table_row.html',
        'partials/_anomalies_table.html',
        'partials/_anomalies_table_row.html',
        'partials/_pagination.html',
    ):
        environment.parse(_read(ALERTS / relative))

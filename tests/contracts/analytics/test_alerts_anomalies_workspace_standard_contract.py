from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ALERTS = ROOT / 'app/templates/analytics/alerts'
PARTIALS = ALERTS / 'partials'


def read(path: Path | str) -> str:
    target = path if isinstance(path, Path) else ROOT / path
    return target.read_text(encoding='utf-8')


def test_alerts_workspace_uses_shared_tabs_and_canonical_url_state() -> None:
    index = read(ALERTS / 'index.html')
    routes = read('app/analytics/routes.py')
    alert_routes = read('app/analytics/alerts/routes.py')

    assert 'analytics/components/_analysis_workspace.html' in index
    assert 'analytics_workspace.tabbed(' in index
    assert "('alerts', 'Alerts'" in index
    assert "('anomalies', 'Anomalies'" in index
    assert "('routing', 'Routing & Suppression'" in index
    assert 'name="tab" value="{{ active_tab }}"' in index
    assert 'data-analytics-preserve-tab' in index
    assert "'/alerts'," in routes
    assert "'/alerts-anomalies'," not in routes
    assert "context['selected_tab'] = _selected_tab()" in alert_routes


def test_alerts_hero_uses_bottom_notice_and_incomplete_evidence_semantics() -> None:
    hero = read(PARTIALS / '_hero.html')

    assert 'page_hero.context_metric(' in hero
    assert 'page_hero.context_bottom_notice(' in hero
    assert 'context_posture_note' not in hero
    assert "posture_value = 'Evidence Incomplete'" in hero
    assert 'do not treat missing evidence as healthy' in hero
    assert 'text-[' not in hero
    assert 'tracking-[' not in hero


def test_alerts_readiness_and_overview_follow_bright_evidence_hierarchy() -> None:
    filters = read(PARTIALS / '_filters.html')
    overview = read(PARTIALS / '_cluster_signal_overview.html')

    assert 'analytics/components/_analysis_surfaces.html' in filters
    assert 'analytics/components/_analysis_workspace.html' in filters
    assert 'analysis_surface.readiness_shell_classes()' in filters
    assert 'Source Evidence Incomplete' in filters
    assert 'analytics/components/_analysis_surfaces.html' in overview
    assert 'Investigation Posture' in overview
    assert 'Operational Reading' in overview
    assert '<article class="bg-surface-card px-4 py-4">' in overview
    assert '<aside class="border-t border-outline-subtle bg-surface-hover' in overview
    assert 'progress_bar' not in overview


def test_alerts_and_anomalies_use_shared_record_collection_and_pagination() -> None:
    alerts_table = read(PARTIALS / '_alerts_table.html')
    anomalies_table = read(PARTIALS / '_anomalies_table.html')
    pagination = read('app/templates/analytics/components/_record_pagination.html')

    for table in (alerts_table, anomalies_table):
        assert 'analytics/components/_evidence_record_list.html' in table
        assert 'analytics/components/_record_pagination.html' in table
        assert 'record_pagination.render(' in table
        assert 'analytics.alerts' in table
        assert 'partials/_pagination.html' not in table

    assert 'href_endpoint' in pagination
    assert 'hx_target' in pagination
    assert '(5, 10, 25, 50)' in pagination


def test_alert_records_are_closed_by_default_and_use_controlled_wrapping() -> None:
    alert_row = read(PARTIALS / '_alerts_table_row.html')
    anomaly_row = read(PARTIALS / '_anomalies_table_row.html')

    for row in (alert_row, anomaly_row):
        assert '@kaori:alerts-collapse.window="expanded = false"' in row
        assert 'x-bind:hidden="!expanded"' in row
        assert 'hidden' in row
        assert 'x-cloak' in row
        assert 'break-all' not in row
        assert 'text-[' not in row
        assert 'tracking-[' not in row


def test_alert_domain_payloads_are_semantic_and_do_not_emit_css_classes() -> None:
    contracts = read('app/analytics/alerts/contracts.py')
    modules = [
        read('app/analytics/alerts/health.py'),
        read('app/analytics/alerts/routing.py'),
        read('app/analytics/alerts/ownership.py'),
        read('app/analytics/alerts/readiness.py'),
        read('app/analytics/alerts/inhibition.py'),
        read('app/analytics/alerts/silences.py'),
        read('app/analytics/alerts/snapshots.py'),
    ]
    labels = read('app/templates/components/table_label.html')

    assert "'class': str" not in contracts
    assert all("'class':" not in module for module in modules)
    assert "'available'" in labels
    assert "'limited'" in labels
    assert "'incident_risk'" in labels


def test_alert_recommendations_use_canonical_tabs() -> None:
    engine = read('app/intelligence/recommendation_engine.py')
    overview = read('app/analytics/overview/service.py')

    assert '/analytics/alerts-anomalies' not in engine
    assert '/analytics/alerts?tab=alerts&severity=critical' in engine
    assert '/analytics/alerts?tab=anomalies' in engine
    assert '/analytics/alerts?tab=readiness' in engine
    assert '/analytics/alerts-anomalies' not in overview

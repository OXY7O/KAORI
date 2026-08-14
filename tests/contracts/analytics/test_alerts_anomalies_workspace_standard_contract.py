import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALERTS = ROOT / 'app/templates/analytics/kubernetes/alerts'
PARTIALS = ALERTS / 'partials'


def read(path: Path | str) -> str:
    target = path if isinstance(path, Path) else ROOT / path
    return target.read_text(encoding='utf-8')


def test_alerts_workspace_uses_shared_tabs_and_canonical_url_state() -> None:
    index = read(ALERTS / 'index.html')
    routes = read('app/analytics/routes.py')
    alert_routes = read('app/analytics/kubernetes/alerts/routes.py')

    assert 'analytics/kubernetes/components/_analysis_workspace.html' in index
    assert 'analytics_workspace.tabbed(' in index
    assert "('alerts', 'Alerts'" in index
    assert "('anomalies', 'Anomalies'" in index
    assert "('routing', 'Routing & Suppression'" in index
    assert 'name="tab" value="{{ active_tab }}"' in index
    assert 'data-analytics-preserve-tab' in index
    assert "'/alerts'," in routes
    assert "'/alerts-anomalies'," not in routes
    assert "context['selected_tab'] = _selected_tab()" in alert_routes


def test_alerts_hero_uses_canonical_context_card_and_evidence_semantics() -> None:
    hero = read(PARTIALS / '_hero.html')

    assert 'page_hero.context_card(' in hero
    assert "('shield-alert', 'Critical Alerts'" in hero
    assert "('shield-check', 'Source Health'" in hero
    assert 'evidence_incomplete' in hero
    assert re.search(r'posture_status\s*=\s*["\']Watch["\']', hero)
    assert re.search(r'posture_tone\s*=\s*["\']warning["\']', hero)
    assert "'Manage Clusters'" in hero
    assert 'context_posture_header' not in hero
    assert 'context_posture_note' not in hero
    assert 'context_bottom_notice' not in hero
    assert 'text-[' not in hero
    assert 'tracking-[' not in hero


def test_alerts_readiness_and_overview_follow_bright_evidence_hierarchy() -> None:
    filters = read(PARTIALS / '_filters.html')
    overview = read(PARTIALS / '_cluster_signal_overview.html')

    assert 'analytics/components/_analysis_surfaces.html' in filters
    assert 'analytics/kubernetes/components/_analysis_workspace.html' in filters
    assert 'analysis_surface.readiness_shell_classes()' in filters
    assert 'Source Evidence Incomplete' in filters
    assert 'analytics/components/_analysis_surfaces.html' in overview
    assert 'data-kaori-cluster-signal-overview' in overview
    assert 'Signal Posture' in overview
    assert 'Investigation Focus' in overview
    assert 'Operator Decision' in overview
    assert 'Evidence Boundary' in overview
    assert 'aria-label="Alert severity profile"' in overview
    assert 'Info Alerts' in overview
    assert 'Evidence Coverage' in overview
    assert 'xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]' in overview
    assert 'xl:grid-cols-6' not in overview
    assert 'Investigation Posture' not in overview
    assert 'progress_bar' not in overview


def test_alerts_and_anomalies_use_shared_record_collection_and_pagination() -> None:
    alerts_table = read(PARTIALS / '_alerts_table.html')
    anomalies_table = read(PARTIALS / '_anomalies_table.html')
    pagination = read('app/templates/analytics/components/_record_pagination.html')

    for table in (alerts_table, anomalies_table):
        assert 'analytics/kubernetes/components/_evidence_record_list.html' in table
        assert 'analytics/components/_record_pagination.html' in table
        assert 'record_pagination.render(' in table
        assert 'analytics.alerts' in table
        assert 'partials/_pagination.html' not in table

    assert 'href_endpoint' in pagination
    assert 'hx_target' in pagination
    assert '(5, 10, 25, 50)' in pagination


def test_alert_records_use_shared_view_more_modals_and_controlled_wrapping() -> None:
    alert_row = read(PARTIALS / '_alerts_table_row.html')
    anomaly_row = read(PARTIALS / '_anomalies_table_row.html')
    modal = read('app/templates/analytics/kubernetes/components/_record_detail_modal.html')

    assert "modal_width = 'max-w-5xl' if size == 'wide' else 'max-w-4xl'" in modal
    assert "size='standard'" in modal
    assert 'max-h-[calc(100dvh-2rem)]' in modal
    assert 'data-kaori-record-detail-modal' in modal
    assert 'relative flex h-[calc(100dvh-1rem)]' not in modal

    for row in (alert_row, anomaly_row):
        assert 'analytics/kubernetes/components/_record_detail_modal.html' in row
        assert '@kaori:alerts-collapse.window="detailOpen = false"' in row
        assert 'record_detail_modal.render(' in row
        assert 'aria-haspopup="dialog"' in row
        assert '<span>View Details</span>' in row
        assert 'panel-top-open' in row
        assert 'expanded = false' not in row
        assert 'x-bind:hidden="!expanded"' not in row
        assert 'View Evidence' not in row
        assert 'Hide Evidence' not in row
        assert 'chevron-down' not in row
        assert 'break-all' not in row
        assert 'text-[' not in row
        assert 'tracking-[' not in row

    assert 'data-kaori-alert-evidence-modal' in alert_row
    assert 'Signal Context' in alert_row
    assert 'Triage Decision' in alert_row
    assert 'Triage Readiness' in alert_row
    assert 'Routing Metadata' in alert_row
    assert 'data-kaori-anomaly-evidence-modal' in anomaly_row
    assert 'Observed Deviation' in anomaly_row
    assert 'Review Decision' in anomaly_row
    assert 'Investigation Sequence' in anomaly_row


def test_alert_domain_payloads_are_semantic_and_do_not_emit_css_classes() -> None:
    contracts = read('app/analytics/kubernetes/alerts/contracts.py')
    modules = [
        read('app/analytics/kubernetes/alerts/health.py'),
        read('app/analytics/kubernetes/alerts/routing.py'),
        read('app/analytics/kubernetes/alerts/ownership.py'),
        read('app/analytics/kubernetes/alerts/readiness.py'),
        read('app/analytics/kubernetes/alerts/inhibition.py'),
        read('app/analytics/kubernetes/alerts/silences.py'),
        read('app/analytics/kubernetes/alerts/snapshots.py'),
    ]
    labels = read('app/templates/components/table_label.html')

    assert "'class': str" not in contracts
    assert all("'class':" not in module for module in modules)
    assert "'available'" in labels
    assert "'limited'" in labels
    assert "'incident_risk'" in labels


def test_alert_recommendations_use_canonical_tabs() -> None:
    engine = read('app/intelligence/recommendation_engine.py')
    overview = read('app/analytics/kubernetes/overview/service.py')

    assert '/analytics/alerts-anomalies' not in engine
    assert '/analytics/alerts?tab=alerts&severity=critical' in engine
    assert '/analytics/alerts?tab=anomalies' in engine
    assert '/analytics/alerts?tab=readiness' in engine
    assert '/analytics/alerts-anomalies' not in overview


def test_alert_boundaries_use_white_structured_boundary_cards() -> None:
    boundary_partials = (
        '_operational_resources.html',
        '_ownership_summary.html',
        '_routing_summary.html',
        '_silence_inhibition_summary.html',
    )

    for name in boundary_partials:
        content = read(PARTIALS / name)
        assert 'analysis_surface.boundary_card(' in content
        assert 'analysis_surface.attention_strip_classes(' not in content

    routing = read(PARTIALS / '_routing_summary.html')
    assert 'Top Grouping Keys' in routing
    assert '{% call analysis_surface.boundary_card(' in routing

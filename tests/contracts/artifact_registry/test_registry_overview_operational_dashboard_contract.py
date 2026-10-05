from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_artifact_registry_overview_consumes_operational_dashboard_family() -> None:
    page = read('app/templates/artifact_registry/overview.html')
    content = read('app/templates/artifact_registry/partials/_overview_content.html')
    hero = read('app/templates/artifact_registry/partials/_overview_hero.html')
    signal = read('app/templates/artifact_registry/partials/_overview_signal_overview.html')

    assert 'artifact_registry/partials/_overview_content.html' in page
    assert 'page_hero.operational_dashboard(' in hero
    assert 'Artifact Registry Operations' in hero
    assert "'Committed Snapshots'" in hero
    assert "url_for('integrations.registry')" in hero

    assert 'components/operational_dashboard_workspace.html' in content
    assert 'dashboard_workspace.controller(' in content
    assert 'dashboard_workspace.navigation(' in content
    assert 'for tab_key, tab_label, tab_icon in dashboard_workspace.standard_tabs' in content
    assert "dashboard_workspace.panel(" in content
    assert "url_for('artifact_registry.overview_section', section=tab_key)" in content
    assert 'hx-trigger="revealed"' in content
    assert 'Preparing committed Artifact Registry dashboard evidence.' in content

    assert 'components/operational_signal_overview.html' in signal
    assert 'signal_overview.render(' in signal
    assert 'components/operational_metric_card.html' in signal
    assert 'hx-push-url="true"' in signal
    assert 'hx-include="#artifact-registry-dashboard-active-tab"' in signal
    assert 'All Registry Providers' in signal
    assert "scope_label='Active Scope'" in signal


def test_artifact_registry_overview_scope_is_committed_and_provider_neutral() -> None:
    routes = read('app/artifact_registry/routes.py')
    presentation = read('app/artifact_registry/presentation.py')
    operations = read('app/templates/artifact_registry/partials/_overview_operations.html')

    assert "request.args.get('provider_id', type=int)" in routes
    assert "request.args.get('tab', 'overview', type=str)" in routes
    assert "request.args.get('provider_health_page', 1)" in routes
    assert 'normalize_dashboard_page_size' in routes
    for section in ('overview', 'capacity', 'signals', 'reporting'):
        assert f"'{section}': 'artifact_registry/partials/_overview_" in routes
    assert 'artifact_registry/partials/_overview_content.html' in routes
    assert 'normalize_operational_tab' in routes
    assert 'normalize_operational_tab(active_tab)' in presentation
    assert 'is_htmx_request(request.headers)' in routes
    assert "@artifact_registry_bp.post('/sync')" in routes
    assert "@permission_required('artifact_registry.sync')" in routes
    assert 'RegistryProject.integration_instance_id == selected_provider.id' in presentation
    assert "registry_metrics_readiness(provider).get('status') == 'ready'" in presentation
    assert 'HarborClient(' not in presentation
    assert 'requests.' not in routes
    assert 'Registry Provider Health Summary' in operations
    assert 'Inventory Snapshot' in operations
    assert 'Data Freshness' in operations


def test_artifact_registry_overview_reuses_shared_sections_and_domain_handoffs() -> None:
    operations = read('app/templates/artifact_registry/partials/_overview_operations.html')
    capacity = read('app/templates/artifact_registry/partials/_overview_capacity.html')
    capacity_snapshot = read('app/templates/artifact_registry/partials/_overview_capacity_snapshot.html')
    forecast = read('app/templates/artifact_registry/partials/_overview_forecast_risk.html')
    consumers = read('app/templates/artifact_registry/partials/_overview_top_consumers.html')
    signals = read('app/templates/artifact_registry/partials/_overview_signals.html')
    alert_guidance = read('app/templates/artifact_registry/partials/_overview_alert_response_guidance.html')
    reporting = read('app/templates/artifact_registry/partials/_overview_reporting.html')
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')

    assert 'components/operational_section_card.html' in operations
    assert 'components/peer_content_grid.html' in operations
    assert 'components/peer_content_grid.html' in capacity
    assert 'components/peer_content_grid.html' in reporting
    for source in (capacity_snapshot, forecast, consumers):
        assert "url_for('artifact_registry.analytics')" in source
    assert 'artifact_registry/partials/_overview_alerts_summary.html' in signals
    assert 'artifact_registry/partials/_overview_alert_response_guidance.html' in signals
    assert 'artifact_registry/partials/_overview_recommended_actions.html' in signals
    for endpoint in (
        "url_for('artifact_registry.security')",
        "url_for('artifact_registry.runtime')",
        "url_for('artifact_registry.governance')",
        "url_for('artifact_registry.analytics')",
        "url_for('intelligence.catalog')",
        "url_for('intelligence.recommendations')",
    ):
        assert endpoint in alert_guidance
    assert 'components/reporting_dashboard_workspace.html' in reporting
    assert 'reporting_workspace.summary(' in reporting
    assert 'reporting_workspace.guidance(' in reporting
    assert "url_for('reports.overview')" in reporting_workspace


def test_operational_dashboard_standard_registers_artifact_registry_consumer() -> None:
    standard = read('docs/design/patterns/OPERATIONAL_DASHBOARD.md')
    verifier = read('scripts/verify_operational_dashboard_standard.py')

    assert 'Artifact Registry → Overview' in standard
    assert 'Artifact Registry Overview is a conforming operational-domain consumer' in standard
    assert 'ARTIFACT_CONTENT' in verifier
    assert '_verify_artifact_registry_dashboard(' in verifier


def test_artifact_registry_operations_overview_matches_reference_dashboard_grammar() -> None:
    operations = read('app/templates/artifact_registry/partials/_overview_operations.html')
    health = read('app/templates/artifact_registry/partials/_overview_provider_health.html')
    signal = read('app/templates/artifact_registry/partials/_overview_signal_overview.html')
    presentation = read('app/artifact_registry/presentation.py')

    assert 'artifact_registry/partials/_overview_provider_health.html' in operations
    assert 'Inventory Snapshot' in operations
    assert 'Data Freshness' in operations
    assert 'overview.inventory_items' in operations
    assert 'overview.freshness' in operations
    assert "current_user.has_permission('artifact_registry.sync')" not in operations
    assert "url_for('artifact_registry.sync_inventory')" not in operations
    assert 'Sync Inventory' not in operations

    for label in (
        'Registry Provider',
        'Overall',
        'Projects',
        'Repositories',
        'Artifacts',
        'Security Signals',
        'Snapshot Sources',
    ):
        assert label in health
    for source in ('Inventory', 'Metrics Source', 'Security Evidence'):
        assert source in health
    assert 'components/pagination.html' in health
    assert "for size in pagination.allowed_per_page" in health
    assert "[5, 10, 25, 50]" not in health

    for label in (
        "'Projects'",
        "'Repositories'",
        "'Artifacts'",
        "'Tags'",
        "'Artifact Footprint'",
        "'Public Projects'",
    ):
        assert label in presentation
    for label in (
        "'Inventory Snapshot'",
        "'Metrics Snapshot'",
        "'Security Snapshot'",
        "'Analytics Snapshot'",
    ):
        assert label in presentation
    assert 'overview.posture.label' in signal
    assert 'overview.posture.tone' in signal


def test_artifact_registry_overview_keeps_reference_information_hierarchy() -> None:
    operations = read('app/templates/artifact_registry/partials/_overview_operations.html')
    health = read('app/templates/artifact_registry/partials/_overview_provider_health.html')
    capacity = read('app/templates/artifact_registry/partials/_overview_capacity.html')
    signals = read('app/templates/artifact_registry/partials/_overview_signals.html')
    reporting = read('app/templates/artifact_registry/partials/_overview_reporting.html')
    presentation = read('app/artifact_registry/presentation.py')

    assert "current_user.has_permission('artifact_registry.sync')" not in operations
    assert "url_for('artifact_registry.sync_inventory')" not in operations
    assert 'Sync Inventory' not in operations
    assert 'Inventory is missing for part of this scope. Queue the inventory worker.' not in operations

    for label in (
        "'Inventory Snapshot'",
        "'Metrics Snapshot'",
        "'Security Snapshot'",
        "'Analytics Snapshot'",
    ):
        assert presentation.count(label) >= 2
    for retired in ("'Inventory Fleet'", "'Metrics Fleet'", "'Security Coverage'", "'Analytics Fleet'"):
        assert retired not in presentation

    assert "loading_bar_id='artifact-registry-provider-health-loading'" in health
    assert 'hx-indicator="#artifact-registry-provider-health-loading"' in health

    assert 'artifact_registry/partials/_overview_capacity_snapshot.html' in capacity
    assert 'artifact_registry/partials/_overview_forecast_risk.html' in capacity
    assert 'artifact_registry/partials/_overview_top_consumers.html' in capacity

    assert 'artifact_registry/partials/_overview_alerts_summary.html' in signals
    assert 'artifact_registry/partials/_overview_alert_response_guidance.html' in signals
    assert 'artifact_registry/partials/_overview_recommended_actions.html' in signals

    assert 'reporting_workspace.summary(' in reporting
    assert reporting.index('reporting_workspace.summary(') < reporting.index('reporting_workspace.guidance(')

    assert 'committed_states = [state for state in states if state.last_committed_at is not None]' in presentation
    build_overview = presentation.split('def build_overview(', 1)[1].split('def _project_row', 1)[0]
    assert "state.status == 'ready' and state.last_committed_at is not None" not in build_overview
    assert "'failed_refresh_count': failed_refresh_count" in presentation
    assert "'capacity': capacity" in presentation
    assert "'alerts': alerts" in presentation
    assert "'recommended_actions': recommended_actions" in presentation
    assert "'reporting': reporting" in presentation


def test_artifact_registry_dashboard_state_semantics_and_jinja_mapping_safety() -> None:
    presentation = read('app/artifact_registry/presentation.py')
    capacity_snapshot = read('app/templates/artifact_registry/partials/_overview_capacity_snapshot.html')
    forecast = read('app/templates/artifact_registry/partials/_overview_forecast_risk.html')
    consumers = read('app/templates/artifact_registry/partials/_overview_top_consumers.html')
    alerts = read('app/templates/artifact_registry/partials/_overview_alerts_summary.html')
    alert_guidance = read('app/templates/artifact_registry/partials/_overview_alert_response_guidance.html')
    recommendations = read('app/templates/artifact_registry/partials/_overview_recommended_actions.html')
    shared_recommendations = read('app/templates/components/operational_recommendation_cards.html')
    shared_alerts = read('app/templates/components/operational_alert_summary.html')
    health = read('app/templates/artifact_registry/partials/_overview_provider_health.html')
    signal = read('app/templates/artifact_registry/partials/_overview_signal_overview.html')
    shared_signal = read('app/templates/components/operational_signal_overview.html')

    assert 'overview.capacity.items' not in capacity_snapshot
    assert 'overview.capacity.metrics' in capacity_snapshot
    assert "'metrics': [" in presentation
    assert "'source_ready': metrics_ready_count > 0" in presentation
    assert "'security_not_applicable': security_not_applicable" in presentation

    assert 'Sync Required' in capacity_snapshot
    assert 'components/states/_empty_state.html' in capacity_snapshot
    for source in (capacity_snapshot, forecast, consumers):
        assert 'components/states/_empty_state.html' in source
        assert 'empty_state_variant = "panel"' in source
    assert 'components/states/_blocked_state.html' not in forecast
    assert 'components/states/_blocked_state.html' not in consumers
    assert 'Source Required' in forecast
    assert 'Sync Required' in forecast
    assert 'Source Required' in consumers
    assert 'Sync Required' in consumers

    assert 'components/operational_alert_summary.html' in alerts
    assert 'data-kaori-alert-insight="stacked"' in shared_alerts
    assert 'Cases Available' in alerts
    assert 'No Findings' in alerts
    assert 'empty_state_tone = "normal"' in shared_alerts
    assert 'overview.alerts.total > 0' in alert_guidance
    assert 'Alert Response Not Required' in alert_guidance
    assert 'No Active Signals' in alert_guidance
    assert 'empty_state_variant = "panel"' in alert_guidance
    assert 'components/states/_empty_state.html' in alert_guidance
    assert 'components/operational_recommendation_cards.html' in recommendations
    assert 'empty_state_variant = "panel"' in shared_recommendations

    assert 'row.security_not_applicable' in health
    assert 'No Artifacts' in health
    assert 'No Registry Providers Available' in health

    assert 'components/operational_signal_overview.html' in signal
    assert 'overview.posture.label' in signal
    assert 'overview.posture.tone' in signal
    assert 'signal_updated' in signal
    assert 'status_indicator_label(status_label, status_tone' in shared_signal

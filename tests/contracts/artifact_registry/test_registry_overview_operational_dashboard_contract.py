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

    assert 'Operational Signal Overview' in signal
    assert 'components/operational_metric_card.html' in signal
    assert 'hx-push-url="true"' in signal
    assert 'hx-include="#artifact-registry-dashboard-active-tab"' in signal
    assert 'All Registry Providers' in signal


def test_artifact_registry_overview_scope_is_committed_and_provider_neutral() -> None:
    routes = read('app/artifact_registry/routes.py')
    presentation = read('app/artifact_registry/presentation.py')
    operations = read('app/templates/artifact_registry/partials/_overview_operations.html')

    assert "request.args.get('provider_id', type=int)" in routes
    assert "request.args.get('tab', 'overview', type=str)" in routes
    assert "request.args.get('provider_health_page', 1)" in routes
    assert "PROVIDER_HEALTH_PAGE_SIZES = {5, 10, 25, 50}" in routes
    for section in ('overview', 'capacity', 'signals', 'reporting'):
        assert f"'{section}': 'artifact_registry/partials/_overview_" in routes
    assert 'artifact_registry/partials/_overview_content.html' in routes
    assert "allowed_tabs = {'overview', 'capacity', 'signals', 'reporting'}" in presentation
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
    signals = read('app/templates/artifact_registry/partials/_overview_signals.html')
    reporting = read('app/templates/artifact_registry/partials/_overview_reporting.html')

    for source in (operations, capacity, signals, reporting):
        assert 'components/operational_section_card.html' in source
    assert 'components/peer_content_grid.html' in operations
    assert 'components/peer_content_grid.html' in capacity
    assert 'components/peer_content_grid.html' in reporting
    assert "url_for('artifact_registry.analytics')" in capacity
    assert "url_for('artifact_registry.security')" in signals
    assert "url_for('artifact_registry.runtime')" in signals
    assert "url_for('artifact_registry.governance')" in signals
    assert "url_for('intelligence.recommendations')" in signals
    assert 'components/reporting_dashboard_workspace.html' in reporting
    assert 'reporting_workspace.guidance(' in reporting
    assert "url_for('reports.overview')" in reporting
    assert 'does not create a parallel reporting subsystem' in reporting


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
    assert "current_user.has_permission('artifact_registry.sync')" in operations
    assert "url_for('artifact_registry.sync_inventory')" in operations

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
    assert "for size in [5, 10, 25, 50]" in health

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
    assert 'Inventory Sync Required' in signal


def test_artifact_registry_overview_keeps_reference_information_hierarchy() -> None:
    operations = read('app/templates/artifact_registry/partials/_overview_operations.html')
    health = read('app/templates/artifact_registry/partials/_overview_provider_health.html')
    capacity = read('app/templates/artifact_registry/partials/_overview_capacity.html')
    signals = read('app/templates/artifact_registry/partials/_overview_signals.html')
    reporting = read('app/templates/artifact_registry/partials/_overview_reporting.html')
    presentation = read('app/artifact_registry/presentation.py')

    assert "current_user.has_permission('artifact_registry.sync')" in operations
    assert "url_for('artifact_registry.sync_inventory')" in operations
    assert 'Sync Inventory' in operations

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

    assert 'components/peer_content_grid.html' in capacity
    assert 'components/operational_callout.html' in capacity
    assert 'Inventory Footprint & Demand' in capacity
    assert 'Analytics Handoff' in capacity
    assert 'unsupported provider capacity is not inferred' in capacity

    assert 'components/peer_content_grid.html' in signals
    assert 'Security & Runtime Signals' in signals
    assert 'Evidence & Actions' in signals
    assert "overview.critical_findings if overview.scanned_count else 'N/A'" in signals
    assert "overview.high_findings if overview.scanned_count else 'N/A'" in signals

    assert reporting.index('Reporting Evidence') < reporting.index('reporting_workspace.guidance(')
    assert 'Reports owns definitions, generation, schedules, retained artifacts, and audit.' in reporting

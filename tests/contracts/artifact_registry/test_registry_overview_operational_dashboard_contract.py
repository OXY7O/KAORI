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
    assert content.count('dashboard_workspace.panel(') == 4
    for tab in ('overview', 'capacity', 'signals', 'reporting'):
        assert f"dashboard_workspace.panel('{tab}'" in content

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
    assert 'artifact_registry/partials/_overview_content.html' in routes
    assert "allowed_tabs = {'overview', 'capacity', 'signals', 'reporting'}" in presentation
    assert 'RegistryProject.integration_instance_id == selected_provider.id' in presentation
    assert "registry_metrics_readiness(provider).get('status') == 'ready'" in presentation
    assert 'HarborClient(' not in presentation
    assert 'requests.' not in routes
    assert 'No provider request is issued by this Overview page.' in operations


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

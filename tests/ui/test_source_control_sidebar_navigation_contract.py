"""Source Control must be visible through KAORI's canonical Integrations navigation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_source_control_is_a_real_integrations_sidebar_capability():
    catalog = _read('app/common/workspace_navigation_catalog.py')
    assert "'integrations.source_control'" in catalog
    assert "'source_control'" in catalog
    assert "'Source Control'" in catalog
    assert "'integrations.secrets_management'" in catalog
    # Sidebar ownership is canonical, not another custom menu component.
    sidebar = _read('app/templates/components/navigation/sidebar.html')
    assert "for child in item['children']" in sidebar


def test_github_workspace_retains_source_control_sidebar_active_state():
    navigation = _read('app/common/workspace_navigation.py')
    assert "'integrations.source_control': 'source_control'" in navigation
    assert "('github_source.', 'source_control')" in navigation
    assert "('github_source_uat.', 'source_control')" in navigation
    assert "'github_source.'" in navigation.split('def _workspace_key(')[1]


def test_source_control_breadcrumb_and_kernel_owner_match():
    breadcrumb = _read('app/common/navigation.py')
    module = _read('app/integrations/source_control/source_control/providers/github/kernel_contract.py')
    assert "'integrations.source_control': 'Source Control'" in breadcrumb
    assert "'github_source.'" in module
    assert "'github_source_uat.'" in module


def test_github_provider_action_uses_shared_provider_selector():
    workspace = _read('app/templates/integrations/partials/_domain_workspace.html')
    taxonomy = _read('app/definitions/catalogs/integrations/taxonomy.yaml')
    assert "domain.key == 'source_control'" in workspace
    module = _read('app/integrations/source_control/source_control/providers/github/kernel_contract.py')
    assert "url_for('integrations.choose_integration_provider', integration_type=item.key)" in workspace
    assert "workspace_endpoint='github_source.index'" in module
    assert 'GitHub · First Provider' not in workspace
    assert 'GitHub · Open Provider' not in workspace
    assert 'workspace_endpoint: integrations.source_control' in taxonomy



def test_provider_chooser_resolves_domain_from_matrix() -> None:
    from app.integrations.navigation import provider_selector_domain

    expected_domains = {
        'source_control': 'source_control',
        'object_storage': 'storage',
        'registry': 'registry',
        'container_orchestrator': 'orchestration',
        'secrets_pki': 'secrets_management',
        'metrics_source': 'observability',
        'alert_source': 'observability',
    }
    for integration_type, domain_key in expected_domains.items():
        domain = provider_selector_domain(integration_type)
        assert domain is not None
        assert domain['key'] == domain_key

    assert provider_selector_domain('unregistered_type') is None


def test_chooser_route_uses_canonical_sidebar_and_breadcrumb_ownership() -> None:
    presentation = _read('app/bootstrap/presentation.py')
    sidebar_model = _read('app/common/workspace_navigation.py')
    breadcrumb = _read('app/common/navigation.py')
    assert "request.endpoint == 'integrations.choose_integration_provider'" in presentation
    assert 'active_capability_override=' in presentation
    assert 'integration_selector_label=' in presentation
    assert "resolved_endpoint == 'integrations.choose_integration_provider'" in sidebar_model
    assert "endpoint in {'integrations.choose_integration_provider', 'integrations.select_metrics_source_provider'}" in breadcrumb
    assert "BreadcrumbItem('Choose Provider')" in breadcrumb



def test_metrics_provider_chooser_stays_with_observability_navigation() -> None:
    presentation = _read('app/bootstrap/presentation.py')
    sidebar = _read('app/common/workspace_navigation.py')
    navigation = _read('app/integrations/navigation.py')
    breadcrumb = _read('app/common/navigation.py')

    assert "request.endpoint == 'integrations.select_metrics_source_provider'" in presentation
    assert "provider_selector_domain('metrics_source')" in presentation
    assert "'integrations.select_metrics_source_provider': 'observability'" in sidebar
    assert "'integrations.select_metrics_source_provider'" in navigation
    assert "'integrations.select_metrics_source_provider'" in breadcrumb
    assert "BreadcrumbItem('Choose Provider')" in breadcrumb

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
    assert 'url_for('integrations.choose_integration_provider', integration_type=item.key)' in workspace
    assert "workspace_endpoint='github_source.index'" in module
    assert 'GitHub · First Provider' not in workspace
    assert 'GitHub · Open Provider' not in workspace
    assert 'workspace_endpoint: integrations.source_control' in taxonomy

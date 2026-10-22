"""Ensure Vault reuses shared Integration provider presentation contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/integrations/secrets_management/vault/index.html'
ROUTES = ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/application/routes.py'


def test_vault_provider_landing_reuses_canonical_provider_components():
    source = TEMPLATE.read_text(encoding='utf-8')
    assert 'integrations/components/_provider_frontpage.html' in source
    assert 'components/integration_workspace_tabs.html' in source
    assert 'provider_front.hero(' in source
    assert 'provider_front.overview(' in source
    assert 'integration_tabs.render("vault", active_tab, registered, registered)' in source
    assert 'Connection Registry' in source
    assert 'Source Qualification Boundaries' in source
    assert "url_for('vault.detail', instance_id=item.id)" in source
    assert 'pagination_ui.numeric_pages' in source
    assert 'Sensitive Secret' not in source


def test_provider_counts_use_canonical_enabled_and_ready_state_only():
    source = ROUTES.read_text(encoding='utf-8')
    assert "IntegrationInstance.lifecycle_status == 'active'" in source
    assert "IntegrationInstance.readiness_status == 'ready'" in source
    assert "tab in {'coverage', 'registry'}" in source
    assert 'per_page=request.args.get(\'per_page\', 5' in source

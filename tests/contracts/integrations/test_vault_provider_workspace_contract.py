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


DETAIL = ROOT / 'app/templates/integrations/secrets_management/vault/detail.html'
VAULT_TEMPLATE_ROOT = ROOT / 'app/templates/integrations/secrets_management/vault'
FORM = VAULT_TEMPLATE_ROOT / 'form.html'


def _partial(name: str) -> str:
    return (VAULT_TEMPLATE_ROOT / 'partials' / name).read_text(encoding='utf-8')


def test_vault_registry_uses_full_table_shared_filters_and_default_five_rows():
    landing = TEMPLATE.read_text(encoding='utf-8')
    routes = ROUTES.read_text(encoding='utf-8')
    for marker in (
        'components/table.html',
        'components/pagination.html',
        'components/table_registry.html',
        'table_ui.inventory_block_header(',
        'data-kaori-vault-full-table-registry',
        'data-kaori-canonical-registry-filter="vault-connections"',
        'hx-trigger="change, input changed delay:400ms, submit"',
        'registry_ui.clear_filters_action(',
        'table_ui.title_cell(',
        'integration_status(validation_state',
        'pagination_ui.numeric_pages(',
        'components/states/_empty_state.html',
    ):
        assert marker in landing
    for field in ('q', 'environment', 'readiness'):
        assert f'name="{field}"' in landing
    assert 'Apply Filters' not in landing
    assert '<noscript>' in landing
    assert "IntegrationInstance.name.icontains(search, autoescape=True)" in routes
    assert "VaultInstance.endpoint.icontains(search, autoescape=True)" in routes
    assert "per_page=request.args.get('per_page', 5" in routes
    assert "registered = query.count()" in routes
    assert "filtered = query" in routes


def test_vault_detail_reuses_four_domain_workspaces_without_cloning_engine():
    detail = DETAIL.read_text(encoding='utf-8')
    for tab in ('configuration', 'validation', 'runtime', 'inventory'):
        assert f'id="vault-panel-{tab}"' in detail
        assert f"activeTab === '{tab}'" in detail
        assert f"partials/_detail_{tab}.html" in detail
    assert "['configuration', 'validation', 'runtime', 'inventory']" in detail
    assert 'components/framed_workspace_tabs.html' in detail
    assert 'id="vault-operational-evidence-title"' in detail
    assert '{% if can_view_secrets_pki %}' in detail
    assert '{% if can_view_cert_analytics %}' in detail

    configuration = _partial('_detail_configuration.html')
    assert 'integrations/components/_provider_configuration_contract.html' in configuration
    assert 'provider_configuration_contract.render(' in configuration
    assert "url_for('vault.edit_instance', instance_id=instance.id)" in configuration
    assert 'SecretID · Encrypted / Not Displayed' in configuration
    assert 'Vault remains authoritative' in configuration

    validation = _partial('_detail_validation.html')
    assert 'components/connection_validation_header.html' in validation
    assert 'integrations/components/_capability_readiness.html' in validation
    assert 'capability_readiness.render(' in validation
    assert 'Vault Full Validation' in validation
    assert "url_for('vault.validate', instance_id=instance.id)" in validation
    assert 'csrf_token()' in validation
    assert 'instance.enabled' in validation

    runtime = _partial('_detail_runtime.html')
    assert 'integrations/components/_runtime_decision.html' in runtime
    assert 'runtime_decision.render(' in runtime
    assert 'latest_runtime_observation' in runtime
    assert 'pagination_ui.numeric_pages(' in runtime
    assert 'table_ui.inventory_block_header(' in runtime
    assert "url_for('vault.runtime_refresh', instance_id=instance.id)" in runtime
    assert 'csrf_token()' in runtime
    assert "['unhealthy', 'sealed', 'uninitialized', 'unavailable']" in runtime

    inventory = _partial('_detail_inventory.html')
    assert 'KV v2 Inventory Evidence' in inventory
    assert 'PKI Public Issuer Evidence' in inventory
    assert 'PKI Stored Certificates' in inventory
    assert 'inventory_readiness.observed_secret_count' in inventory
    assert "current_user.has_permission('jobs.view')" in inventory
    assert 'No Secret values or private key material' in inventory


def test_vault_registration_reuses_actions_without_changing_proof_or_credentials():
    form = FORM.read_text(encoding='utf-8')
    routes = ROUTES.read_text(encoding='utf-8')
    for token in (
        'integrations/components/_provider_registration_hero.html',
        'integrations/components/_provider_edit_hero.html',
        'components/action_button.html',
        'components/info_tip.html',
        'data-kaori-vault-connection-form',
        "form.connection_test_proof",
        'form.secret_id',
        'form.hidden_tag()',
        'value="test"',
        'value="save"',
    ):
        assert token in form
    assert 'action_button.classes(' in form
    assert "verified_secret(proof, values, int(current_user.id))" in routes
    assert "issue_proof(values, int(current_user.id))" in routes
    assert "enqueue_instance_validation(" in routes
    assert "enqueue_runtime_health_refresh(" in routes
    assert 'IntegrationRuntimeObservation.query.filter_by(' in routes
    assert 'latest_runtime_observation=latest_runtime_observation' in routes

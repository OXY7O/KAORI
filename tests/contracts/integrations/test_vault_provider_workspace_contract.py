"""Ensure Vault reuses shared Integration provider presentation contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/integrations/secrets_management/vault/index.html'
ROUTES = ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/application/routes.py'
SERVICE = ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/application/service.py'


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
    assert 'registry_ui.footer(' in source
    assert 'Sensitive Secret' not in source


def test_provider_counts_use_canonical_enabled_and_ready_state_only():
    routes = ROUTES.read_text(encoding='utf-8')
    service = SERVICE.read_text(encoding='utf-8')
    assert "IntegrationInstance.lifecycle_status == 'active'" in service
    assert "IntegrationInstance.readiness_status == 'ready'" in service
    assert 'list_vault_connection_registry(' in routes
    assert "tab in {'coverage', 'registry'}" in routes
    assert "per_page=request.args.get('per_page', 5" in routes


DETAIL = ROOT / 'app/templates/integrations/secrets_management/vault/detail.html'
VAULT_TEMPLATE_ROOT = ROOT / 'app/templates/integrations/secrets_management/vault'
FORM = VAULT_TEMPLATE_ROOT / 'form.html'


def _partial(name: str) -> str:
    return (VAULT_TEMPLATE_ROOT / 'partials' / name).read_text(encoding='utf-8')


def test_vault_registry_uses_full_table_shared_filters_and_default_five_rows():
    landing = TEMPLATE.read_text(encoding='utf-8')
    routes = ROUTES.read_text(encoding='utf-8')
    service = SERVICE.read_text(encoding='utf-8')
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
        'registry_ui.footer(',
        'components/states/_empty_state.html',
    ):
        assert marker in landing
    for field in ('q', 'environment', 'readiness'):
        assert f'name="{field}"' in landing
    assert 'Apply Filters' not in landing
    assert '<noscript>' in landing
    assert 'IntegrationInstance.name.icontains(search, autoescape=True)' in service
    assert 'VaultInstance.endpoint.icontains(search, autoescape=True)' in service
    assert "per_page=request.args.get('per_page', 5" in routes
    assert 'registered = query.count()' in service
    assert 'filtered = query' in service
    assert 'list_vault_connection_registry(' in routes


def test_vault_detail_reuses_four_domain_workspaces_without_cloning_engine():
    detail = DETAIL.read_text(encoding='utf-8')
    for tab in ('configuration', 'validation', 'runtime', 'inventory'):
        assert f'id="vault-panel-{tab}"' in detail
        assert f"activeTab === '{tab}'" in detail
        assert f'partials/_detail_{tab}.html' in detail
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
        'form.connection_test_proof',
        'form.secret_id',
        'form.hidden_tag()',
        'value="test"',
        'value="save"',
    ):
        assert token in form
    assert 'action_button.classes(' in form
    assert 'verified_secret(proof, values, int(current_user.id))' in routes
    assert 'issue_proof(values, int(current_user.id))' in routes
    assert 'enqueue_instance_validation(' in routes
    assert 'enqueue_runtime_health_refresh(' in routes
    service = SERVICE.read_text(encoding='utf-8')
    assert 'IntegrationRuntimeObservation.query.filter_by(' in service
    assert 'latest_vault_runtime_observation(instance.id)' in routes
    assert 'latest_runtime_observation=latest_runtime_observation' in routes


def test_vault_readiness_metadata_follows_existing_integration_lock():
    validation = _partial('_detail_validation.html')
    assert '{% set capability_metadata = [' in validation
    assert "'Profile · Vault AppRole' if is_ready else 'No Committed Validation'" in validation
    assert 'capability_metadata,' in validation


def test_vault_registration_and_edit_match_shared_kaori_connection_form() -> None:
    from jinja2 import Environment

    form = FORM.read_text(encoding='utf-8')
    source = ROUTES.read_text(encoding='utf-8')
    shared_actions = (ROOT / 'app/templates/integrations/components/_provider_registration_actions.html').read_text(
        encoding='utf-8'
    )
    shared_context = (ROOT / 'app/templates/integrations/components/_provider_registration_context.html').read_text(
        encoding='utf-8'
    )

    for component in (
        'integrations/components/_provider_registration_context.html',
        'integrations/components/_provider_registration_actions.html',
        'components/connection_validation_header.html',
        'components/form_action_bar.html',
        'components/operational_toggle.html',
        'integrations/components/_workspace.html',
    ):
        assert component in form

    for structure in (
        'id="vault-connection-form"',
        'xl:grid-cols-12 xl:items-start',
        'xl:col-span-8',
        'xl:col-span-4 xl:sticky',
        'Connection Identity',
        'Endpoint & Access',
        'AppRole Authentication',
        'Optional Evidence Scope',
        'Transport &amp; Operational Controls',
        'connection_validation_header.render(',
        'operational_toggle.render(',
        'provider_registration_context.render(',
        'provider_registration_actions.render(',
        'form_action_bar.render(',
        'info_tip.render(',
    ):
        assert structure in form
    assert 'list-inside list-disc' not in form
    assert 'mt-auto flex flex-wrap gap-2' not in form
    assert 'components/info_flow.html' in shared_context
    assert 'components/related_page_card.html' in shared_context
    assert 'data-kaori-provider-registration-actions' in shared_actions

    # Vault submits synchronously, unlike Harbor's HTMX form test.
    # Reuse the verified registration footer without changing server routes.
    assert 'name="action"' in form
    assert 'value="test"' in form
    assert 'value="save"' in form
    assert "connectionVerified: {{ 'true' if proof else 'false' }}" in form
    assert 'x-ref' in form and 'connectionProof' in form
    assert 'x-on:input.capture="invalidateConnectionTest($event)"' in form
    assert 'x-on:change.capture="invalidateConnectionTest($event)"' in form
    assert "this.$refs.connectionProof.value = ''" in form
    assert 'x-bind:disabled="!connectionVerified"' in form
    assert 'disabled\n' in shared_actions
    assert 'form.connection_test_proof(value=proof or ""' in form
    assert 'verified_secret(proof, values, int(current_user.id))' in source
    assert 'issue_proof(values, int(current_user.id))' in source
    assert "action == 'test'" in source
    assert "action == 'save'" in source

    # Credential and optional collection semantics stay explicit in both modes.
    for field in (
        'form.name',
        'form.environment',
        'form.description',
        'form.endpoint',
        'form.namespace',
        'form.timeout',
        'form.auth_mount_mode',
        'form.auth_mount',
        'form.role_id',
        'form.secret_id',
        'form.kv2_mounts',
        'form.pki_mounts',
        'form.pki_stored_certs_enabled',
        'form.enabled',
    ):
        assert field in form
    assert 'autocomplete="new-password"' in form
    assert 'On Edit, a blank SecretID retains the encrypted credential' in form
    assert "placeholder='Leave blank to retain stored SecretID' if instance else 'Enter AppRole SecretID'" in form
    assert 'if instance else' in form
    assert 'KV v2' in form and 'PKI' in form
    assert 'no_store/imported' in form
    assert 'Full Validation' in form
    assert "url_for('vault.detail', instance_id=instance.id)" in form
    assert 'url_for("vault.index")' in form

    # Keep the user-visible descriptions concise at the canonical desktop width
    # without clipping or altering the shared responsive layout.
    assert 'Vault owns Secrets; KAORI governs evidence.' in form
    assert 'Disabled connections stay registered, not used.' in form
    assert 'whitespace-nowrap' not in form

    # AppRole is the only implemented auth method. The mount path is not a
    # different auth method: default and controlled custom paths share one
    # approved provider client without an unsupported Auth API.
    forms = (ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/application/forms.py').read_text(
        encoding='utf-8'
    )
    assert 'auth_mount_mode = SelectField(' in forms
    assert "('approle', 'Default AppRole Mount (approle)')" in forms
    assert "('custom', 'Custom AppRole Mount')" in forms
    assert 'form.auth_mount_mode' in form
    assert "**{'x-model': 'authMountMode'}" in form
    assert 'x-show="authMountMode === \'custom\'"' in form
    assert 'x-cloak' in form
    assert "**{':required': \"authMountMode === 'custom'\"}" in form
    assert "validate_auth_mount(str(field.data or ''))" in forms
    assert "if self.auth_mount_mode.data == 'approle':" in forms
    assert 'if self.is_submitted() and not self.auth_mount_mode.raw_data:' in forms
    assert 'form.auth_mount_mode.errors' in form
    assert 'form.auth_mount.errors' in form
    assert 'AppRole Authentication' in form

    # Shared form title/Guide composition replaces field-level prose.
    assert "info_tip.render('vault-approle-auth-guide'" in form
    assert "info_tip.render('vault-evidence-scope-guide'" in form
    assert 'Default for most Vault installations. Custom mounts are supported.' not in form
    assert 'Use the AppRole path configured in Vault. One segment only' not in form
    assert 'Metadata-only KV v2; empty disables collection.' not in form
    assert 'Public PKI issuer metadata; empty disables collection.' not in form
    assert 'Enter mount names separated by commas.' in form
    assert 'KV v2: up to eight mounts' in form
    assert 'PKI: up to four mounts' in form
    assert 'form.kv2_mounts.label.text' in form
    assert 'form.pki_mounts.label.text' in form
    assert "kv2_mounts = StringField('Approved KV v2 Mounts'," in forms
    assert "pki_mounts = StringField('Approved PKI Mounts'," in forms
    assert "'Vault Namespace'," in forms
    assert "'Vault Namespace (optional)'" not in forms

    # Placeholders are field-level render_kw defaults, so Add and Edit share
    # them without duplicating markup or obscuring existing saved values.
    for placeholder in (
        'e.g. Vault X300',
        'Describe the connection purpose (optional)',
        'https://vault.example.internal:8200',
        'e.g. team-platform (Enterprise only)',
        'Paste AppRole RoleID',
        'Enter AppRole SecretID',
    ):
        assert placeholder in forms
    assert 'placeholder="secret, team-kv"' in form
    assert 'placeholder="pki, pki-internal"' in form
    assert 'placeholder="kaori-approle"' in form

    # Test Connection and rejected Register/Edit actions use the canonical
    # top-right Operational Toast + Activity Audit, not a form-level banner.
    assert 'operational_callout.render(' not in form
    assert 'if message' not in form
    assert "'vault-evidence-scope-guide'" in form
    assert 'No optional inventory is collected.' in form
    assert 'def _form_feedback(' in source
    assert "delivery_policy='audit_only'" in source
    assert 'queue_feedback=True' in source
    assert "event_type='vault_connection_test'" in source
    assert "event_type='vault_connection_test_failed'" in source
    assert "event_type='vault_connection_update_test'" in source
    assert "event_type='vault_connection_update_test_failed'" in source
    assert "event_type='vault_connection_registered'" in source
    assert "event_type='vault_connection_updated'" in source
    assert "event_type='vault_registration_proof_rejected'" in source
    assert "event_type='vault_connection_update_proof_rejected'" in source
    assert "event_type='vault_connection_registration_failed'" in source
    assert "event_type='vault_connection_update_failed'" in source
    assert 'message=message,\n        notification_context=_notification()' not in source

    # A rejected form must identify safe invalid field names, without a
    # generic no-context toast or a new page-local error notification.
    assert 'def _form_validation_message(' in source
    assert 'form = VaultConnectionForm()' in source
    assert "'secret_id': 'AppRole SecretID'" in source
    assert "'csrf_token' in errors" in source
    assert '_form_validation_message(form, action=' in source
    assert 'Review the highlighted fields before testing or registering.' not in source
    assert 'Review the highlighted fields before testing or saving.' not in source
    assert "if action == 'test' or not self.connection_test_proof.data:" in forms
    assert "{% set invalid_focus_field = (form.errors|list|first) if form.errors else '' %}" in form
    # Jinja requires ordinary keywords before dynamic **kwargs; an
    # autofocus keyword *after* x-model / :required breaks template parsing.
    # Use a formatter-stable expression, not a nested parenthesized call.
    assert "autofocus=invalid_focus_field == 'secret_id'" in form
    assert form.count('autofocus=invalid_focus_field == ') == 10
    assert "autofocus=invalid_focus_field == 'auth_mount_mode', **{'x-model': 'authMountMode'}" in form
    assert (
        "autofocus=invalid_focus_field == 'auth_mount', **{':required': \"authMountMode === 'custom'\"}"
        in form
    )
    assert 'autofocus=(invalid_focus_field' not in form

    Environment().parse(form)

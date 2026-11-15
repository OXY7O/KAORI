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
    assert 'id="vault-operational-evidence-title"' not in detail
    assert 'id="vault-detail-tabs"' in detail
    assert "url_for('secrets_pki." not in detail

    configuration = _partial('_detail_configuration.html')
    assert 'integrations/components/_provider_configuration_contract.html' in configuration
    assert 'Requires approved scope and read-only metadata access.' in configuration
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
    assert 'integrations/components/_validation_poller.html' in validation
    assert 'integrations/components/_provider_job_status.html' in validation
    assert 'integrations/components/_readiness_explanation.html' in validation
    assert 'id="vault-core-validation"' in validation
    assert 'hx-target="#vault-core-validation"' in validation
    assert 'validation_poller.render(' in validation
    assert 'provider_job_status.render(' in validation
    assert 'readiness_explanation.render(' in validation
    assert 'integration_status(' not in validation
    assert 'partials/_capability_registry.html' in validation
    assert 'Validation task:' not in validation

    capability_table = _partial('_capability_registry.html')
    assert 'components/table.html' in capability_table
    assert 'components/table_label.html' in capability_table
    assert 'data-kaori-capability-table-standard' in capability_table
    assert '"health"' in capability_table
    assert '"approle"' in capability_table
    assert '"token_lookup"' in capability_table
    assert '"mount_metadata"' in capability_table
    assert 'GET /v1/sys/mounts' in capability_table
    assert 'permission_unavailable' in capability_table

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
    assert '{% set capability_metadata = ' in validation
    assert "'No Committed Validation'" in validation
    assert "'Profile · '" in validation
    assert 'capability_metadata,' in validation
    # Historical Vault compatibility may be Degraded while required APIs are
    # observed; optional mount discovery is never a required readiness gate.
    assert "readiness in ['ready', 'degraded']" in validation
    assert "summary.get('mount_metadata') == 'available'" in validation
    assert "required_ready ~ ' / ' ~ required_total" in validation


def test_vault_full_validation_matches_shared_htmx_job_and_evidence_contract() -> None:
    from jinja2 import Environment

    validation = _partial('_detail_validation.html')
    registry = _partial('_capability_registry.html')
    source = ROUTES.read_text(encoding='utf-8')
    for component in (
        'components/connection_validation_header.html',
        'integrations/components/_validation_poller.html',
        'integrations/components/_provider_job_status.html',
        'integrations/components/_capability_readiness.html',
        'integrations/components/_readiness_explanation.html',
        'integrations/components/_provider_detail_posture.html',
        'components/framed_workspace_tabs.html',
        'components/operation_feedback_oob.html',
    ):
        assert component in validation
    for marker in (
        'id="vault-core-validation"',
        'hx-post="{{ url_for(\'vault.validate\', instance_id=instance.id) }}"',
        'hx-target="#vault-core-validation"',
        'hx-swap="outerHTML"',
        'hx-disabled-elt="button"',
        'hx-indicator="#vault-validation-loading"',
        "url_for('vault.validation_status'",
        'validation_poller.render(',
        'provider_job_status.render(',
        'readiness_explanation.render(',
        'capability_readiness.render(',
        'framed_workspace_tabs.badge_oob(',
        'provider_detail_posture.state_oob(',
    ):
        assert marker in validation
    for old_fragment in (
        'Validation task:',
        "instance.validation_message or 'No capability",
        'Permission Unavailable',
    ):
        assert old_fragment not in validation

    assert 'data-kaori-capability-table-standard' in registry
    assert 'components/table.html' in registry
    assert registry.count('"required": true') == 3
    assert registry.count('"required": false') == 1
    assert 'permission_unavailable' in registry
    assert 'get_validation_snapshot' not in registry
    assert "summary.get('mount_metadata')" in registry

    assert 'def validation_status(instance_id: int, task_id: str)' in source
    assert 'validate_snapshot_access(' in source
    assert 'snapshot_feedback_for_user(snapshot, user_id=int(current_user.id))' in source
    assert 'validation_poll_response(content, snapshot=snapshot)' in source
    assert "is_htmx = request.headers.get('HX-Request') == 'true'" in source
    assert 'queue_feedback=not is_htmx' in source

    Environment().parse(validation)
    Environment().parse(registry)


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
    assert "autofocus=invalid_focus_field == 'auth_mount', **{':required': \"authMountMode === 'custom'\"}" in form
    assert 'autofocus=(invalid_focus_field' not in form

    Environment().parse(form)

def test_vault_policy_guide_and_capability_explorer_reuse_shared_kaori_contracts() -> None:
    from jinja2 import Environment

    configuration = _partial('_detail_configuration.html')
    policy = _partial('_minimum_validation_policy.html')
    validation = _partial('_detail_validation.html')
    registry = _partial('_capability_registry.html')
    routes = ROUTES.read_text(encoding='utf-8')

    assert 'partials/_minimum_validation_policy.html' in configuration
    assert 'Minimum Vault Permission &amp; Policy Example' in policy
    assert 'integrations/components/_record_detail_modal.html' in policy
    assert 'integrations/components/_record_actions.html' in policy
    for endpoint in ('auth/token/lookup-self', 'sys/mounts', 'approved-kv-mount/metadata'):
        assert endpoint in policy
    assert 'capabilities = ["read", "list"]' in policy
    assert 'capabilities = ["read"]' in policy
    assert 'capabilities = ["list"]' in policy
    assert 'path "approved-kv-mount/data' not in policy
    assert 'Core API readiness is independent of Secret and PKI inventory.' in validation

    for shared in (
        'components/table_registry.html',
        'components/pagination.html',
        'components/loading_bar.html',
        'integrations/components/_record_actions.html',
        'integrations/components/_record_detail_modal.html',
        'components/states/_empty_state.html',
        'data-kaori-capability-server-filtered',
        'data-kaori-capability-table-standard',
        'data-kaori-vault-capability-record',
        "hx-target=\"#vault-capability-registry\"",
        'capability_page',
        'capability_per_page',
        'capability_q',
        'capability_requirement',
        'capability_status',
        'record_actions.view_more(',
        'pagination_ui.numeric_pages(',
    ):
        assert shared in registry
    assert registry.count('"required": true') == 3
    assert registry.count('"required": false') == 1
    assert "readiness in ['ready', 'degraded']" in registry
    assert 'permission_unavailable' in registry
    assert 'page_size = requested_page_size if requested_page_size in [5, 10, 25, 50] else 5' in registry
    assert "@vault_bp.get('/instances/<int:instance_id>/capabilities')" in routes
    assert "@permission_required('integrations.manage')\ndef capability_registry(" in routes
    assert "instance = _instance_or_404(instance_id)" in routes

    for template in (policy, registry, validation):
        Environment().parse(template)

def test_vault_capability_modal_parity_with_kubernetes_without_invented_checks() -> None:
    from jinja2 import Environment

    registry = _partial('_capability_registry.html')
    modal = _partial('_capability_detail_content.html')
    adapter = (
        ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/adapter.py'
    ).read_text(encoding='utf-8')

    # Retain one provider-owned native modal per visible capability row.
    assert 'integrations/components/_record_detail_modal.html' in registry
    assert 'integrations/secrets_management/vault/partials/_capability_detail_content.html' in registry
    assert "record_detail_modal.render(" in registry
    assert "row.key" in registry
    assert 'data-kaori-vault-capability-detail' not in registry

    for section in (
        'data-kaori-capability-modal-v3',
        'data-kaori-capability-decision-summary',
        'data-kaori-capability-contract-snapshot',
        'data-kaori-capability-validation-evidence',
        'data-kaori-capability-operational-decision',
        'data-kaori-capability-governance-boundary',
        'data-kaori-capability-verification-command',
        'data-kaori-capability-verification-unavailable',
    ):
        assert section in modal
    for title in (
        'Capability Decision',
        'Contract Snapshot',
        'Validation Evidence',
        'Operational Decision',
        'Operational Impact',
        'Recommended Action',
        'Governance Boundary',
        'Verification Command',
    ):
        assert title in modal

    # Three evidence dimensions explain real adapter facts, not three
    # independent persisted per-capability checks which Vault does not store.
    assert "('01', 'API Contract'," in modal
    assert "('02', 'Identity & Access'," in modal
    assert "('03', 'Committed Observation'," in modal
    assert 'not three independently stored check results' in modal
    assert "result.status_label" in modal
    assert 'result.observed' in modal
    assert 'result.limited' in modal
    assert 'result.gap' in modal
    assert 'Capability Not Observed' in modal
    assert "['health', 'approle', 'token_lookup']" in adapter
    assert "'mount_metadata': capability['mount_metadata']" in adapter

    # A standalone human CLI check cannot claim to validate the managed
    # AppRole. Show copyable commands only for safe, read-only operator probes.
    assert "row.key == 'approle'" in modal
    assert "verification_command = ''" in modal
    assert 'data-kaori-capability-verification-unavailable' in modal
    assert 'Use Run Full Validation with the approved managed AppRole identity.' in modal
    for probe in (
        'vault status -format=json',
        'vault token lookup -format=json',
        'vault read -format=json sys/mounts',
    ):
        assert probe in modal
    for unsafe in (
        'VAULT_TOKEN=',
        'role_id=',
        'secret_id=',
        'vault write auth/',
        'vault kv get',
        'vault token create',
        'curl -k',
    ):
        assert unsafe not in modal

    Environment().parse(registry)
    Environment().parse(modal)

def test_vault_view_more_copy_line_budgets_cover_all_capabilities_and_statuses() -> None:
    import re

    from jinja2 import Environment

    modal = _partial('_capability_detail_content.html')
    registry = _partial('_capability_registry.html')

    # All four Vault API rows use this one partial and keep semantic status
    # distinctions. No individual capability gets an independent modal layout.
    assert '{% for result in page_rows %}' in registry
    assert 'partials/_capability_detail_content.html' in registry
    for key in ("'health'", "'approle'", "'token_lookup'", "'mount_metadata'"):
        assert key in registry
    for state in ('result.observed', 'result.limited', 'result.gap'):
        assert state in modal
    assert 'Capability Not Observed' in modal

    # Desktop line budgets are backed by concise provider-aware copy rather
    # than truncating meaningful operational facts. Mobile retains wrapping.
    for name, expected_count, max_chars in (
        ('decision_message', 4, 80),
        ('auth_boundary', 4, 24),
        ('auth_description', 4, 64),
        ('observation_description', 4, 64),
    ):
        variants = re.findall(r"\\{% set " + name + r" = '([^']*)' %\\}", modal)
        assert len(variants) == expected_count, name
        assert max(map(len, variants)) <= max_chars, name

    assert 'lg:line-clamp-1" title="{{ decision_message }}"' in modal
    assert "{% if label == 'Identity Boundary' %}lg:line-clamp-1{% endif %}" in modal
    assert 'lg:line-clamp-2" title="{{ description }}"' in modal
    assert "('03', 'Committed Observation', result.status_label, observation_description)" in modal
    assert "('03', 'Committed Observation', result.status_label, decision_message)" not in modal

    contract_copy = re.search(r"\\('01', 'API Contract', row.contract, '([^']*)'\\)", modal)
    assert contract_copy is not None
    assert len(contract_copy.group(1)) <= 64

    verification_headers = re.findall(
        r'<p class="mt-1 text-xs leading-5 text-content-secondary lg:line-clamp-1">([^<]+)</p>',
        modal,
    )
    assert len(verification_headers) == 2  # CLI example and AppRole safe fallback
    assert all(len(line) <= 64 for line in verification_headers)
    assert 'No copyable login command or SecretID is provided.' in modal

    Environment().parse(modal)
    Environment().parse(registry)


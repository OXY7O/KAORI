from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_harbor_workspace_is_reachable_from_registry_domain_without_product_navigation() -> None:
    provider = read('app/integrations/registry/providers/harbor/__init__.py')
    bootstrap = read('app/bootstrap/blueprints.py')
    navigation = read('app/common/navigation.py')

    assert "workspace_endpoint='harbor.index'" in provider
    assert "navigation_endpoint_prefixes=('harbor.',)" in provider
    assert "/integrations/registry/harbor/instances/{instance.id}" in provider
    assert 'harbor_bp' in bootstrap
    assert "'Harbor'" not in navigation


def test_harbor_registration_reuses_canonical_connection_workflow() -> None:
    form = read('app/templates/integrations/registry/providers/harbor/instance_form.html')
    registration = read('app/integrations/registry/providers/harbor/application/registration.py')
    service = read('app/integrations/registry/providers/harbor/application/service.py')

    assert 'Register Harbor Connection' in form
    assert 'Connection Configuration' in form
    assert 'Test Connection' in form
    assert 'Register Connection' in form
    assert 'grid-cols-12' in form
    assert 'xl:col-span-8' in form
    assert 'xl:col-span-4' in form
    assert 'connectionVerified' in form
    assert 'provider_registration_hero.render' in form
    assert 'after_save_label="Full Validation"' in form
    assert 'after_save_description="Then validate compatibility and capabilities"' in form
    assert 'provider_registration_actions.render' in form
    assert 'REGISTRATION_PROOF_MAX_AGE_SECONDS = 600' in registration
    assert "'password'," in registration
    assert "canonical.readiness_status = 'validation_required'" in service
    assert 'client.test_connection()' in service


def test_harbor_authentication_fields_follow_selected_auth_mode() -> None:
    form = read('app/templates/integrations/registry/providers/harbor/instance_form.html')
    forms = read('app/integrations/registry/providers/harbor/application/forms.py')

    assert "authType: {{ (form.auth_type.data or 'basic')|tojson|forceescape }}" in form
    assert "**{'x-model':'authType'}" in form
    assert 'class="contents"' not in form
    assert form.count('x-show="authType === \'basic\'"') == 1
    assert 'x-show="authType === \'basic\'"' in form
    assert "class=\"mt-4 grid gap-4 md:grid-cols-2\"" in form
    assert "**{':required':\"authType === 'basic'\"}" in form
    assert "**{':required':\"authType === 'basic' && \" + ('false' if instance is defined and instance else 'true')}" in form
    assert 'x-cloak' in form
    assert 'Ignored when Anonymous / Public Read-Only is selected.' not in form
    assert 'Stored encrypted and never emitted into validation evidence.' not in form
    assert 'Blank preserves the existing encrypted password.' not in form
    assert "('basic', 'Basic Authentication')" in forms
    assert "('anonymous', 'Anonymous / Public Read-Only')" in forms
    assert "if auth_type == 'anonymous':" in forms
    assert 'username = None' in forms
    assert 'password = None' in forms
    registration_actions = read('app/templates/integrations/components/_provider_registration_actions.html')
    assert 'Connection Test Required' in registration_actions
    assert 'Complete Test Connection before registration.' in registration_actions


def test_harbor_registration_copy_is_concise_and_preserves_authority_boundaries() -> None:
    form = read('app/templates/integrations/registry/providers/harbor/instance_form.html')
    index = read('app/templates/integrations/registry/providers/harbor/index.html')

    assert 'Configure Harbor identity, API access, TLS trust, and request controls. Full Validation owns readiness.' in form
    assert 'Configure Harbor API v2.0 access and test identity/reachability. Full Validation establishes readiness.' in form
    assert 'Disabled connections remain registered but are not resolved for use.' in form
    assert 'Harbor executes Registry APIs; KAORI owns normalized identity, evidence, readiness, runtime, and audit.' in form
    assert 'How KAORI registers a reusable Registry connection.' in form
    assert 'How changes restore Registry provider readiness.' in form
    assert (
        'Register Harbor once; committed Registry inventory, Metrics Source bindings, webhook readiness, '
        'and provider validation remain independent.'
    ) in index


def test_harbor_degraded_full_validation_is_not_presented_as_validation_required() -> None:
    validation = read(
        'app/templates/integrations/registry/providers/harbor/partials/_detail_validation.html'
    )
    runtime = read('app/templates/integrations/registry/providers/harbor/partials/_detail_runtime.html')
    presentation = read('app/integrations/registry/providers/harbor/application/presentation.py')
    compatibility = read('app/definitions/catalogs/integrations/compatibility.yaml')

    assert '{% elif readiness == "degraded" %}' in validation
    assert '{% set readiness_label = "Degraded" %}' in validation
    assert '{% set gate_label = "Eligible with Attention" %}' in validation
    assert 'Required contracts are complete; release is in Extended Support.' in validation
    assert (
        'Plan an upgrade to a current qualified Harbor release, then rerun Full Validation '
        'to refresh compatibility and readiness evidence.'
    ) in validation
    assert 'Why Readiness Is Degraded' in validation
    assert 'Resolve Harbor gaps, then rerun Full Validation.' not in validation
    assert "if readiness == 'degraded':" in presentation
    assert "'label': 'Degraded'" in presentation
    assert "{'value': 'degraded', 'label': 'Degraded'}" in presentation
    assert 'runtime_state.readiness == "degraded"' in runtime
    assert 'This provider remains usable with degraded compatibility.' in runtime

    assert 'key: extended_supported' in compatibility
    assert 'readiness: degraded' in compatibility
    assert 'key: harbor-extended' in compatibility
    assert "version_constraint: '>=2.4.1,<2.13'" in compatibility
    assert 'key: harbor-current' in compatibility
    assert "version_constraint: '>=2.13,<2.16'" in compatibility


def test_harbor_validation_and_authority_copy_is_compact() -> None:
    configuration = read(
        'app/templates/integrations/registry/providers/harbor/partials/_detail_configuration.html'
    )
    validation = read(
        'app/templates/integrations/registry/providers/harbor/partials/_detail_validation.html'
    )

    assert 'Harbor remains authoritative for native Registry state and policies.' in configuration
    assert 'Harbor API base URL for read-only discovery, identity, compatibility, capabilities, and Registry evidence.' in configuration
    assert (
        'Harbor owns Registry state and policy; KAORI owns registration, validation evidence, '
        'runtime observation, governance, and audit.'
    ) in configuration
    assert (
        "('Bind Metrics', 'Bind Prometheus/Thanos through Metrics Source for current and long-term "
        "Registry analytics.', 'chart-spline')"
    ) in configuration
    assert (
        'setup_reference_template="integrations/registry/providers/harbor/partials/'
        '_minimum_validation_access.html"'
    ) in configuration
    access_reference = read(
        'app/templates/integrations/registry/providers/harbor/partials/_minimum_validation_access.html'
    )
    assert 'Minimum Harbor API Access Example' in access_reference
    assert 'Open Access Examples' in access_reference
    assert "setTab(tab) { this.activeTab = tab; }" in access_reference
    assert "const tabs = ['baseline', 'optional'];" in access_reference
    assert 'Required API reads:' in access_reference
    assert 'GET /api/v2.0/systeminfo' in access_reference
    assert 'Optional Metadata Reader' in access_reference
    assert 'Harbor role and permission labels can differ by qualified release.' in access_reference
    assert 'Required Harbor readiness and read-capability evidence.' in validation
    assert 'Optional capability evidence; does not affect readiness.' in validation
    assert (
        'Resolve the identified Harbor API, authorization, or compatibility gaps, then rerun '
        'Full Validation to refresh committed readiness evidence.'
    ) in validation

    assert (
        'Required Harbor API identity, compatibility, health, and read capability evidence '
        'for the qualified release.'
    ) not in validation
    assert 'Optional follow-on capability evidence observed without affecting readiness.' not in validation


def test_harbor_detail_uses_shared_provider_domains_with_inventory_lifecycle() -> None:
    detail = read('app/templates/integrations/registry/providers/harbor/instance_detail.html')
    configuration = read(
        'app/templates/integrations/registry/providers/harbor/partials/_detail_configuration.html'
    )
    validation = read(
        'app/templates/integrations/registry/providers/harbor/partials/_detail_validation.html'
    )
    runtime = read('app/templates/integrations/registry/providers/harbor/partials/_detail_runtime.html')
    inventory = read('app/templates/integrations/registry/providers/harbor/partials/_detail_scope.html')

    assert "x-data=\"integrationWorkspaceTabs(['configuration', 'validation', 'runtime', 'inventory']" in detail
    assert 'framed_workspace_tabs.render' in detail
    for label in ('Configuration', 'Validation & Capabilities', 'Runtime & History', 'Inventory & Lifecycle'):
        assert label in detail
    assert 'integrations/registry/providers/harbor/partials/_detail_scope.html' in detail
    assert 'integrations/registry/providers/harbor/partials/_delete_modal.html' in detail
    assert 'Inventory &amp; Lifecycle Decision' in inventory
    assert 'Snapshot freshness, Registry evidence, observability, reconciliation, and deletion guardrails at a glance.' in inventory
    assert 'Snapshot Freshness' in inventory
    assert 'Lifecycle Gate' in inventory
    assert 'KAORI Operational Consumers' in inventory
    assert 'Bound Observability Sources' in read(
        'app/templates/integrations/registry/providers/harbor/partials/_binding_registry.html'
    )
    assert 'Review Harbor configuration, validation, and runtime evidence.' in detail
    assert '"Harbor API read contracts"' in detail
    assert 'provider_detail_posture.render' in detail
    assert 'provider_configuration_contract.render' in configuration
    assert 'connection_validation_header.render' in validation
    assert 'capability_readiness.render' in validation
    assert 'validation_poller.render' in validation
    assert 'harbor-validation-loading' in validation
    assert 'provider_job_status.render' in runtime
    assert 'runtime_decision.render' in runtime
    assert 'integrations/partials/_runtime_history.html' in runtime


def test_harbor_registry_and_capabilities_use_standard_pagination_with_default_five() -> None:
    registry = read('app/templates/integrations/registry/providers/harbor/partials/_registry.html')
    capabilities = read(
        'app/templates/integrations/registry/providers/harbor/partials/_capability_registry.html'
    )
    presentation = read('app/integrations/registry/providers/harbor/application/presentation.py')
    routes = read('app/integrations/registry/providers/harbor/application/routes.py')

    assert 'integrations/components/_provider_registry.html' in registry
    assert 'provider_registry.registry_header' in registry
    assert 'provider_registry.pagination_footer' in registry
    assert 'swap="outerHTML"' in registry
    assert 'pagination_ui.numeric_pages' in capabilities
    assert 'Not Observed' in capabilities
    assert 'per_page: int = 5' in presentation
    assert 'capability_per_page: int = 5' in presentation
    assert 'history_per_page: int = 5' in presentation
    assert "request.args.get('per_page', 5" in routes


def test_harbor_test_connection_full_validation_and_runtime_remain_separate() -> None:
    routes = read('app/integrations/registry/providers/harbor/application/routes.py')
    workspace_web = read('app/integrations/registry/providers/harbor/application/workspace_web.py')
    validation = read('app/integrations/registry/providers/harbor/validation.py')
    runtime = read('app/integrations/registry/providers/harbor/runtime.py')

    assert "@harbor_bp.post('/instances/test-connection')" in routes
    assert 'identity and reachability only' in routes
    assert 'enqueue_instance_validation(' in workspace_web
    assert "integration_type='registry'" in workspace_web
    assert 'enqueue_runtime_health_refresh(' in workspace_web
    assert 'evaluate_compatibility(' in validation
    assert "'runtime_health'" in runtime
    assert 'validate_source(' not in runtime


def test_harbor_workspace_does_not_add_provider_mutation_or_secret_evidence() -> None:
    routes = read('app/integrations/registry/providers/harbor/application/routes.py')
    client = read('app/integrations/registry/providers/harbor/client.py')
    validation = read('app/integrations/registry/providers/harbor/validation.py')

    assert '@harbor_bp.delete' not in routes
    assert '@harbor_bp.put' not in routes
    assert '@harbor_bp.patch' not in routes
    assert 'requests.post(' not in client
    assert 'requests.put(' not in client
    assert 'requests.patch(' not in client
    assert 'requests.delete(' not in client
    assert "'password'" not in validation


def test_harbor_optional_capabilities_do_not_count_as_required_readiness_gaps() -> None:
    presentation = read('app/integrations/registry/providers/harbor/application/presentation.py')
    validation = read(
        'app/templates/integrations/registry/providers/harbor/partials/_detail_validation.html'
    )

    assert "row_status = 'ready' if available else ('blocked' if definition.required else 'degraded')" in presentation
    assert "'required_missing_count': len(required_keys) - required_ready_count" in presentation
    assert "'optional_ready_count': optional_ready_count" in presentation
    assert 'Required Capability Coverage' in validation
    assert 'Required Gaps' in validation
    assert 'Optional Observed' in validation


def test_registry_is_exposed_in_canonical_integrations_sidebar_capabilities() -> None:
    catalog = read('app/common/workspace_navigation_catalog.py')

    integrations_section = catalog.split("key='integrations'", 1)[1].split("key='access'", 1)[0]
    assert "'registry'," in integrations_section
    assert "'Registry'," in integrations_section
    assert "'package'," in integrations_section
    assert "'integrations.registry'," in integrations_section
    assert "('integrations.manage',)" in integrations_section


def test_object_storage_analytics_dependency_path_keeps_metrics_and_alert_evidence_visible() -> None:
    blocker = read('app/templates/storage/object_storage/analytics/partials/_dependency_blocker.html')
    shared = read('app/templates/components/dependencies/_blocker.html')

    assert '"Metrics Source"' in blocker
    assert '"Alert Source"' in blocker
    assert 'Alertmanager or qualified metrics-backed alert evidence' in blocker
    assert 'Object Storage → Metrics Source → Alert Source' in blocker
    assert 'Object Storage → Metrics Source → Alert Source → Analytics Snapshot' in blocker
    assert 'Prometheus-compatible operational metrics source' in blocker
    assert 'Alertmanager when available' in blocker
    assert 'components/provider_prerequisite/_setup_blocker.html' not in blocker
    assert 'dependency_blocked_step = 4' in blocker
    assert 'dependency_blocked_step|default(dependency_blocker.stage|int)' in shared



def test_registry_domain_exposes_parent_context_guidance() -> None:
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')

    assert "'Registry Authority and Evidence'" in workspace
    assert 'Registry providers remain authoritative for repositories, artifacts, native policies' in workspace
    assert 'Harbor is the first qualified Registry provider' in workspace
    assert 'provider-neutral Registry contracts' in workspace
    assert "'integration-' ~ domain.key ~ '-workspace-guidance'" in workspace



def test_harbor_frontpage_hero_uses_canonical_copy_budget() -> None:
    index = read('app/templates/integrations/registry/providers/harbor/index.html')

    assert 'Register Harbor connections with governed readiness and evidence.' in index
    assert (
        'Register and validate reusable Harbor Registry connections while Harbor remains authoritative '
        'for native registry state.'
    ) not in index
    assert len('Register Harbor connections with governed readiness and evidence.') <= 68
    assert len('Register Harbor connections with governed readiness and evidence.'.split()) == 8



def test_harbor_frontpage_matches_canonical_provider_workspace_hierarchy() -> None:
    index = read('app/templates/integrations/registry/providers/harbor/index.html')
    coverage = read('app/templates/integrations/registry/providers/harbor/partials/_coverage.html')
    registry = read('app/templates/integrations/registry/providers/harbor/partials/_registry.html')

    assert 'components/integration_workspace_tabs.html' in index
    assert '"label": "Needs Attention"' in index
    assert '"label": "Consumer Bindings"' not in index
    assert 'integration_tabs.render("harbor"' in index
    assert 'Harbor Integration Coverage' in coverage
    assert 'Harbor Connection Registry' in registry
    assert 'No Consumer Binding Surface Yet' not in index
    assert 'committed Registry inventory' in index
    assert 'Metrics Source bindings' in index
    assert 'webhook readiness' in index


def test_harbor_coverage_keeps_independent_registry_readiness_planes() -> None:
    coverage = read('app/templates/integrations/registry/providers/harbor/partials/_coverage.html')
    presentation = read('app/integrations/registry/providers/harbor/application/presentation.py')

    for label in ('Harbor API', 'Inventory', 'Metrics Source', 'Webhook', 'Coverage'):
        assert label in coverage or label in read(
            'app/templates/integrations/components/_provider_registry.html'
        )
    assert '_provider_status(instance)' in presentation
    assert 'inventory_eligibility = registry_inventory_eligibility(identity)' in presentation
    assert '_inventory_status(collection, eligibility=inventory_eligibility)' in presentation
    assert '_metrics_status(metrics)' in presentation
    assert '_webhook_status(webhook)' in presentation
    assert "coverage_label = 'Complete' if complete else 'Partial'" in presentation



def test_harbor_coverage_does_not_force_desktop_horizontal_scroll() -> None:
    coverage = read('app/templates/integrations/registry/providers/harbor/partials/_coverage.html')

    assert 'overflow-x-auto' not in coverage
    assert "table_ui.table_classes('min-w-[" not in coverage
    assert 'table_ui.table_classes()' in coverage
    assert 'class="min-w-0"' in coverage



def test_harbor_inventory_lifecycle_reuses_asset_owner_contract_without_provider_mutation() -> None:
    detail = read('app/templates/integrations/registry/providers/harbor/instance_detail.html')
    inventory = read('app/templates/integrations/registry/providers/harbor/partials/_detail_scope.html')
    binding_registry = read('app/templates/integrations/registry/providers/harbor/partials/_binding_registry.html')
    modal = read('app/templates/integrations/registry/providers/harbor/partials/_delete_modal.html')
    shared_modal = read('app/templates/integrations/components/_asset_owner_delete_modal.html')
    presentation = read('app/integrations/registry/providers/harbor/application/presentation.py')
    service = read('app/integrations/registry/providers/harbor/application/service.py')
    routes = read('app/integrations/registry/providers/harbor/application/routes.py')
    deletion = read('app/integrations/deletion.py')

    assert 'Inventory & Lifecycle' in detail
    assert 'data-kaori-harbor-inventory-lifecycle' in inventory
    assert 'Inventory &amp; Lifecycle Decision' in inventory
    assert 'Removed With Connection' in inventory
    assert 'Retained After Removal' in inventory
    assert 'Next Lifecycle Action' in inventory
    assert 'Delete Connection' in inventory
    assert "url_for('harbor.delete_instance'" in inventory
    assert "url_for('artifact_registry.inventory')" not in inventory
    assert 'asset_owner_delete_modal.render(' in modal
    assert 'This action cannot be undone.' in shared_modal

    assert "asset_type='registry_instance'" in presentation
    assert 'build_bound_observability_source_rows(' in presentation
    assert 'asset_owner_deletion_guard(' in presentation
    assert 'binding_per_page: int = 5' in presentation
    assert 'RegistryProject.query' not in presentation
    assert 'HarborClient(' not in presentation

    assert 'def delete_harbor_instance(' in service
    assert 'asset_owner_deletion_guard(' in service
    assert "IntegrationBinding.asset_type == 'registry_instance'" in service
    assert 'db.session.delete(canonical)' in service
    assert 'Harbor projects' in routes
    assert "@harbor_bp.post('/instances/<int:instance_id>/delete')" in routes
    assert "@harbor_bp.get('/instances/<int:instance_id>/bindings/registry')" in routes
    assert 'def asset_owner_deletion_guard(' in deletion
    assert 'JobExecution.scope_type == asset_type' in deletion
    assert 'asset_owner_sources.render(' in binding_registry


def test_harbor_inventory_lifecycle_keeps_artifact_registry_as_detail_owner() -> None:
    inventory = read('app/templates/integrations/registry/providers/harbor/partials/_detail_scope.html')
    presentation = read('app/integrations/registry/providers/harbor/application/presentation.py')
    sync = read('app/artifact_registry/sync.py')

    assert 'Open Artifact Registry' not in inventory
    assert (
        'Use Artifact Registry for committed artifact evidence. Manage Metrics Source and Alertmanager bindings in '
        'Observability; Harbor remains read-only for binding changes.'
    ) in inventory
    assert (
        'Detailed Projects, Repositories, Artifacts, Security, Runtime Usage, Governance, '
        'and Analytics remain owned by Artifact Registry.'
    ) in inventory
    assert "key: int(raw_counts.get(key) or 0)" in presentation
    for key in ("'projects'", "'repositories'", "'artifacts'", "'tags'"):
        assert key in presentation
        assert key in sync
    assert 'client.' not in inventory
    assert 'list_projects' not in presentation
    assert 'list_repositories' not in presentation

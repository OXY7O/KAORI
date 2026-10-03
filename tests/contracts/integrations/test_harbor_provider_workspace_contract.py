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
    assert 'after_save_description="Then establish compatibility and capability readiness"' in form
    assert 'provider_registration_actions.render' in form
    assert 'REGISTRATION_PROOF_MAX_AGE_SECONDS = 600' in registration
    assert "'password'," in registration
    assert "canonical.readiness_status = 'validation_required'" in service
    assert 'client.test_connection()' in service


def test_harbor_detail_uses_shared_provider_domains_without_premature_inventory_surface() -> None:
    detail = read('app/templates/integrations/registry/providers/harbor/instance_detail.html')
    configuration = read(
        'app/templates/integrations/registry/providers/harbor/partials/_detail_configuration.html'
    )
    validation = read(
        'app/templates/integrations/registry/providers/harbor/partials/_detail_validation.html'
    )
    runtime = read('app/templates/integrations/registry/providers/harbor/partials/_detail_runtime.html')

    assert "x-data=\"integrationWorkspaceTabs(['configuration', 'validation', 'runtime']" in detail
    assert 'framed_workspace_tabs.render' in detail
    assert 'Configuration' in detail
    assert 'Validation & Capabilities' in detail
    assert 'Runtime & History' in detail
    assert 'Inventory & Lifecycle' not in detail
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

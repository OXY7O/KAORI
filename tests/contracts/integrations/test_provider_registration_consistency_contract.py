from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_observability_coverage_uses_asset_language_and_route_owned_authorization() -> None:
    coverage = read('app/templates/components/integration_coverage_content.html')
    registry = read('app/templates/integrations/components/_provider_registry.html')
    assert "item_label='Assets'" in coverage or 'item_label="Assets"' in coverage
    assert 'Consumer Asset' in registry
    assert 'empty_state_show_admin_required' not in coverage
    assert 'empty_state_permission' not in coverage


def test_prometheus_and_alertmanager_empty_registry_actions_do_not_duplicate_route_authz() -> None:
    for path in (
        'app/templates/integrations/prometheus/partials/_inventory_content.html',
        'app/templates/integrations/alertmanager/partials/_inventory_content.html',
    ):
        text = read(path)
        assert 'Register Connection' in text
        assert 'empty_state_show_admin_required' not in text
        assert 'empty_state_permission' not in text


def test_minio_registration_matches_connection_test_interaction_contract() -> None:
    template = read('app/templates/minio/instance_form.html')
    routes = read('app/minio/routes.py')
    assert 'connection_validation_header.render(' in template
    assert 'minio-connection-test-loading' in template
    assert 'minio-connection-test-result' in template
    assert 'minio.test_new_instance_connection' in template
    assert 'x-on:minio-connection-tested.window' in template
    assert 'integrations/components/_provider_registration_hero.html' in template
    assert 'Register Connection' in template
    assert 'def test_new_instance_connection' in routes
    assert 'minio-connection-tested' in routes


def test_provider_registration_heroes_share_one_canonical_contract() -> None:
    shared = read('app/templates/integrations/components/_provider_registration_hero.html')
    registrations = {
        'Kubernetes': read('app/templates/cluster/add.html'),
        'Prometheus': read('app/templates/prometheus/instance_form.html'),
        'Alertmanager': read('app/templates/alertmanager/instance_form.html'),
        'MinIO': read('app/templates/minio/instance_form.html'),
    }

    for marker in (
        'data-kaori-provider-registration-hero',
        'Registration Posture',
        'Pre-save Requirements',
        'Draft',
        'Before Save',
        'Test Connection',
        'Registration reuses the verified payload',
        'After Save',
        'Core Validation',
        'Then assign consumer bindings',
        'Back to Registry',
    ):
        assert marker in shared

    for provider, template in registrations.items():
        assert 'integrations/components/_provider_registration_hero.html' in template, provider
        assert 'provider_registration_hero.render(' in template, provider

    assert 'Register Kubernetes Connection' in registrations['Kubernetes']
    assert 'Add Kubernetes Connection' not in registrations['Kubernetes']
    assert 'Register Prometheus Connection' in registrations['Prometheus']
    assert 'Register Alertmanager Connection' in registrations['Alertmanager']
    assert 'Register MinIO Connection' in registrations['MinIO']


def test_provider_registration_context_is_shared_and_limited_to_two_context_surfaces() -> None:
    shared = read('app/templates/integrations/components/_provider_registration_context.html')
    registrations = {
        'Kubernetes': read('app/templates/cluster/add.html'),
        'Prometheus': read('app/templates/prometheus/instance_form.html'),
        'Alertmanager': read('app/templates/alertmanager/instance_form.html'),
        'MinIO': read('app/templates/minio/instance_form.html'),
    }

    assert 'data-kaori-provider-registration-context' in shared
    assert 'info_flow.render(' in shared
    assert 'related_page_card.render(' in shared
    assert 'Related Operational Workspace' in shared
    assert 'information_guide_card' not in shared
    assert 'context_guidance_card' not in shared

    for provider, template in registrations.items():
        assert 'integrations/components/_provider_registration_context.html' in template, provider
        assert 'provider_registration_context.render(' in template, provider

    assert 'Kubernetes RBAC & Access Contract' not in registrations['Kubernetes']
    assert 'Connection Identity & Contract' not in registrations['Prometheus']
    assert 'After Registration' not in registrations['Prometheus']
    assert 'Connection Identity & Contract' not in registrations['Alertmanager']
    assert 'After Registration' not in registrations['Alertmanager']
    assert 'Connection Identity & Contract' not in registrations['MinIO']
    assert 'After Registration' not in registrations['MinIO']


def test_frontpage_refactor_keeps_overview_and_kubernetes_filter_contracts_typed() -> None:
    routes = read('app/integrations/routes.py')
    frontpage = read('app/integrations/kubernetes_frontpage.py')

    overview_call = routes.split('def overview()', 1)[1].split('def _render_domain_page', 1)[0]
    for retired_argument in (
        'coverage_query=',
        'coverage_environment=',
        'coverage_status=',
        'coverage_page=',
        'coverage_per_page=',
    ):
        assert retired_argument not in overview_call

    assert 'OperationalPosture' in frontpage
    assert 'def _provider_posture(source: Any | None, binding: Any | None) -> OperationalPosture:' in frontpage
    assert 'def _inventory_coverage(readiness: str) -> OperationalPosture:' in frontpage
    assert 'tuple[OperationalPosture, OperationalPosture, OperationalPosture]' in frontpage

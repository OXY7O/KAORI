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


def test_provider_registration_actions_and_placeholders_are_consistent() -> None:
    kubernetes = read('app/templates/cluster/add.html') + read('app/templates/cluster/partials/_form.html')
    kubernetes_form = read('app/cluster/forms.py')
    prometheus = read('app/templates/prometheus/instance_form.html')
    prometheus_form = read('app/prometheus/forms.py')
    alertmanager = read('app/templates/alertmanager/instance_form.html')
    minio = read('app/templates/minio/instance_form.html')
    minio_form = read('app/minio/forms.py')

    for provider, template in {
        'Kubernetes': kubernetes,
        'Prometheus': prometheus,
        'Alertmanager': alertmanager,
        'MinIO': minio,
    }.items():
        assert 'Cancel' in template, provider
        assert 'Register Connection' in template, provider

    assert 'Run Test Connection successfully before KAORI enables Register Connection.' in kubernetes
    assert 'Run Test Connection successfully before KAORI enables Register Connection.' in prometheus
    assert 'Run Test Connection successfully before KAORI enables Register Connection.' in alertmanager
    assert 'Run Test Connection successfully before KAORI enables Register Connection.' in minio

    assert "'Connection Name'" in kubernetes_form
    assert "'placeholder': 'Kubernetes Production'" in kubernetes_form
    assert "'placeholder': 'Operational purpose and ownership context'" in kubernetes_form

    assert "'Connection Name'" in prometheus_form
    assert "'placeholder': 'Prometheus Production'" in prometheus_form
    assert "'placeholder': 'https://prometheus.example.internal'" in prometheus_form
    assert "'placeholder': 'service-account'" in prometheus_form
    assert "'placeholder': 'Enter bearer token'" in prometheus_form
    assert 'Enter password' in prometheus

    assert 'Connection Name</label>' in alertmanager
    assert 'placeholder="Alertmanager Production"' in alertmanager
    assert 'placeholder="Operational purpose and ownership context"' in alertmanager
    assert 'placeholder="https://alertmanager.example.internal"' in alertmanager
    assert 'placeholder="service-account"' in alertmanager
    assert 'Enter password' in alertmanager
    assert 'Enter bearer token' in alertmanager
    for retired_microcopy in (
        'Use a stable operational name',
        'What this controls:',
        'Allowed range: 1–30 seconds.',
        'Do not append',
    ):
        assert retired_microcopy not in alertmanager

    assert "'placeholder': 'MinIO Production'" in minio_form
    assert "'placeholder': 'Operational purpose and ownership context'" in minio_form
    assert "'placeholder': 'https://minio.example.internal'" in minio_form
    assert "'placeholder': 'minio-reader'" in minio_form
    assert "'placeholder': 'Enter secret key'" in minio_form


def test_minio_connection_test_separates_s3_access_from_product_identity() -> None:
    client = read('app/integrations/minio/client.py')
    service = read('app/minio/service.py')
    routes = read('app/minio/routes.py')
    adapter = read('app/integrations/minio/adapter.py')

    assert 'client.list_buckets()' in client
    assert 's3:ListAllMyBuckets' in client
    assert '/minio/health/live' in client
    assert 'identity_evidence' in client
    assert 'def _client_error_message' in client
    assert 'def _probe_minio_liveness' in client
    assert "if result.product != 'minio'" not in service
    assert 'Product identity and release compatibility remain authoritative Core Validation evidence' in service
    assert 'message=str(exc)' in routes
    assert 'identity_evidence' in adapter

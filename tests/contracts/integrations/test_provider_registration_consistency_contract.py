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
    assert 'Back to Registry' in template
    assert 'Register Connection' in template
    assert 'def test_new_instance_connection' in routes
    assert 'minio-connection-tested' in routes

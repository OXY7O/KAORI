from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_minio_index_uses_canonical_provider_registry_shell() -> None:
    index = read('app/templates/minio/index.html')
    tabs = read('app/templates/components/integration_workspace_tabs.html')
    registry = read('app/templates/minio/partials/_registry_content.html')

    assert 'MinIO Integrations' in index
    assert 'Register Connection' in index
    assert 'MinIO Integration Overview' in index
    assert 'integration_workspace_tabs' in index
    assert 'Integration Coverage' in tabs
    assert 'Connection Registry' in tabs
    assert 'No MinIO Connections Found' in registry


def test_minio_registration_matches_shared_connection_workflow() -> None:
    form = read('app/templates/minio/instance_form.html')

    assert 'Register MinIO Connection' in form
    assert 'Connection Configuration' in form
    assert 'Test Connection' in form
    assert 'Register Connection' in form
    assert 'grid-cols-12' in form
    assert 'xl:col-span-8' in form
    assert 'xl:col-span-4' in form
    assert 'connectionVerified' in form


def test_minio_detail_uses_same_four_provider_workspace_domains() -> None:
    detail = read('app/templates/minio/instance_detail.html')

    assert 'x-data="integrationWorkspaceTabs(' in detail
    assert 'framed_workspace_tabs.render' in detail
    for label in ('Configuration', 'Core Validation', 'Runtime & History', 'Bindings & Consumers'):
        assert label in detail
    assert 'MinIO Integration' in detail
    assert 'Connection Posture' in detail


def test_minio_bindings_expose_metrics_and_alert_consumer_profiles() -> None:
    scope = read('app/templates/minio/partials/_detail_scope.html')
    validation = read('app/templates/minio/partials/_detail_validation.html')

    assert 'Consumer Binding Registry' in scope
    assert 'Prometheus Metrics Consumer' in scope
    assert 'Alertmanager Alert Consumer' in scope
    assert 'minio-metrics-2024-v1' in scope
    assert 'minio-alerts-v1' in scope
    assert 'MinIO Core Validation' in validation
    assert 'Consumer Validation Boundary' in validation
    assert 'missing consumer stream' in validation.lower()

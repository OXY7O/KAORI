from pathlib import Path


def test_canonical_runtime_models_exist():
    source = Path('app/models/integration.py').read_text()
    assert 'class IntegrationInstance' in source
    assert 'class IntegrationBinding' in source
    assert 'class KubernetesConnection' in source


def test_analytics_dependency_uses_provider_neutral_resolution():
    source = Path('app/analytics/common/dependencies.py').read_text()
    assert 'resolve_kubernetes_for_cluster' in source
    assert 'cluster.prometheus_config' not in source


def test_scheduled_runtime_refresh_does_not_use_legacy_prometheus_config():
    source = Path('app/integrations/runtime/tasks.py').read_text()
    assert 'PrometheusInstance' in source
    assert 'PrometheusConfig' not in source


def test_inventory_and_analytics_templates_do_not_format_datetime():
    roots = [Path('app/templates/inventory'), Path('app/templates/analytics')]
    forbidden = ('strftime(', 'astimezone(', 'isoformat(')
    offenders = []
    for root in roots:
        for path in root.rglob('*.html'):
            text = path.read_text()
            if any(token in text for token in forbidden):
                offenders.append(str(path))
    assert not offenders, offenders


def test_runtime_observation_has_canonical_fk():
    source = Path('app/models/integration_runtime.py').read_text()
    assert 'integration_instance_id' in source

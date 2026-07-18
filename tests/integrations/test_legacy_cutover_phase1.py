from pathlib import Path


def _source(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_prometheus_runtime_write_path_is_instance_authoritative():
    source = _source('app/prometheus/service.py')
    assert 'PrometheusConfig.query' not in source
    assert 'cluster.prometheus_config' not in source
    assert 'PrometheusBinding(' not in source
    assert 'PrometheusInstance(' in source
    assert 'ensure_canonical_instance' in source
    assert 'bind_instance' in source


def test_prometheus_routes_do_not_fallback_to_cluster_relationship():
    source = _source('app/prometheus/routes.py')
    assert 'cluster.prometheus_config' not in source
    assert 'or cluster.prometheus_config' not in source


def test_prometheus_client_and_runtime_adapter_are_instance_only():
    client = _source('app/prometheus/client.py')
    adapter = _source('app/prometheus/runtime_adapter.py')
    assert 'PrometheusConfig' not in client
    assert 'PrometheusConfig' not in adapter
    assert 'PrometheusInstance' in client
    assert 'PrometheusInstance' in adapter


def test_integrations_overview_reads_standalone_provider_instances():
    source = _source('app/integrations/service.py')
    assert 'PrometheusConfig.query' not in source
    assert 'AlertmanagerConfig.query' not in source
    assert 'PrometheusInstance.query' in source
    assert 'resolve_instance_for_cluster' in source
    assert 'resolve_alertmanager_sources' in source

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_alertmanager_active_path_uses_canonical_bindings() -> None:
    repository = source('app/alertmanager/repository.py')
    bindings = source('app/alertmanager/bindings.py')
    resolver = source('app/alertmanager/resolver.py')
    service = source('app/alertmanager/service.py')

    assert 'IntegrationBinding' in repository
    assert 'IntegrationBinding' in bindings
    assert 'IntegrationBinding' in resolver
    assert 'AlertmanagerBinding.query' not in repository
    assert 'AlertmanagerConfig.query' not in service
    assert 'get_legacy_config_by_cluster_id' not in service
    assert 'AlertmanagerConfig | AlertmanagerInstance' not in service


def test_kubernetes_connection_is_the_only_read_authority() -> None:
    kubernetes = source('app/integrations/kubernetes/resolver.py')
    cluster_service = source('app/cluster/service.py')

    assert 'return cluster.kubeconfig' not in kubernetes
    assert 'cluster.kubeconfig' not in cluster_service
    assert 'cluster.kubeconfig' not in cluster_service
    assert 'KubernetesConnection' in cluster_service


def test_alertmanager_connection_consumers_are_instance_only() -> None:
    for path in (
        'app/integrations/alertmanager/client_factory.py',
        'app/integrations/alertmanager/reader.py',
        'app/integrations/alertmanager/status.py',
        'app/integrations/alertmanager/validation.py',
    ):
        content = source(path)
        assert 'AlertmanagerConfig' not in content
        assert 'AlertmanagerInstance' in content

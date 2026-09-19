from types import SimpleNamespace

from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api import validation


class _FakeCoreApi:
    api_client = object()

    @staticmethod
    def list_node():
        return SimpleNamespace(items=[object()])


class _FakeDiscovery:
    def __init__(self, api_client):
        self.api_client = api_client

    @staticmethod
    def discover():
        return {
            'api_profile': 'kubernetes-core-v1',
            'compatibility_status': 'compatible',
            'readiness_status': 'ready',
            'features': {},
            'selected_adapters': {},
            'blocked_features': [],
            'legacy_features': [],
            'optional_blocked_features': [],
        }


def _client_for(version: str):
    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        @staticmethod
        def connect():
            return _FakeCoreApi()

        @staticmethod
        def version_api():
            return SimpleNamespace(
                get_code=lambda: SimpleNamespace(
                    git_version=version,
                    platform='linux/amd64',
                )
            )

    return _FakeClient


def _run(monkeypatch, version: str):
    monkeypatch.setattr(validation, 'KubernetesClient', _client_for(version))
    monkeypatch.setattr(validation, 'KubernetesDiscovery', _FakeDiscovery)
    return validation.test_cluster_connection('apiVersion: v1')


def test_extended_lifecycle_degrades_ready_discovery(monkeypatch):
    result = _run(monkeypatch, 'v1.34.6')

    assert result['compatibility_status'] == 'compatible_with_warnings'
    assert result['readiness_status'] == 'degraded'
    assert result['lifecycle_status'] == 'extended'
    assert result['compatibility_profile'] == 'kubernetes-core-v1'
    assert 'Extended lifecycle support' in result['validation_message']


def test_end_of_life_lifecycle_blocks_ready_discovery(monkeypatch):
    result = _run(monkeypatch, 'v1.22.17')

    assert result['compatibility_status'] == 'end_of_life'
    assert result['readiness_status'] == 'blocked'
    assert result['lifecycle_status'] == 'end_of_life'
    assert result['compatibility_profile'] == 'kubernetes-core-v1'
    assert 'older than the KAORI 5-year lifecycle anchor' in result['validation_message']


def test_future_unverified_lifecycle_degrades_without_version_branching(monkeypatch):
    result = _run(monkeypatch, 'v1.38.0')

    assert result['compatibility_status'] == 'unverified_version'
    assert result['readiness_status'] == 'degraded'
    assert result['lifecycle_status'] == 'unknown'
    assert result['compatibility_profile'] == 'kubernetes-core-v1'
    assert 'no definition band currently qualifies this version' in result['validation_message']

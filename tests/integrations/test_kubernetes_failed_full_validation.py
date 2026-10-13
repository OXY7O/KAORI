"""Kubernetes Full Validation failures cannot retain previously Ready provider state."""

from types import SimpleNamespace

import pytest

from app.kubernetes.cluster import service


def _run(monkeypatch, result):
    canonical = SimpleNamespace(readiness_status='ready')
    connection = SimpleNamespace(
        kubeconfig='config',
        server='https://cluster.invalid',
        verify_ssl=True,
        allow_weak_tls=False,
        readiness_status='ready',
        compatibility_status='compatible',
        compatibility_profile='kubernetes-core-v1',
        lifecycle_status='current',
        discovery_summary={'features': {'inventory.pods': {'status': 'ready'}}},
        validation_message='Previously ready',
        last_validated_at=None,
        integration_instance=canonical,
    )
    cluster = SimpleNamespace(
        kubernetes_connection=connection,
        status='connected',
        last_check=None,
        node_count=3,
    )
    commits = []
    monkeypatch.setattr(service, 'connection_for_cluster', lambda _cluster: connection)
    monkeypatch.setattr(service, 'test_cluster_connection', lambda **_kw: result)
    monkeypatch.setattr(
        service,
        '_sync_kubernetes_runtime',
        lambda _cluster: setattr(canonical, 'readiness_status', connection.readiness_status),
    )
    monkeypatch.setattr(
        service,
        'db',
        SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append(1))),
    )
    response = service.run_test_cluster(cluster)
    assert len(commits) == 1
    return response, connection, canonical, cluster


@pytest.mark.parametrize('error', ['Connection timed out', 'Unauthorized'])
def test_failed_full_validation_supersedes_old_provider_ready(monkeypatch, error):
    _response, connection, canonical, cluster = _run(monkeypatch, {'success': False, 'error': error})
    assert cluster.status == 'failed'
    assert connection.readiness_status == canonical.readiness_status == 'blocked'
    assert connection.compatibility_status == 'validation_failed'
    assert connection.compatibility_profile is None
    assert connection.discovery_summary is None
    assert connection.last_validated_at is not None
    assert error in connection.validation_message


def test_subsequent_success_restores_provider_core_evidence(monkeypatch):
    _response, connection, canonical, cluster = _run(
        monkeypatch,
        {
            'success': True,
            'node_count': 2,
            'version': 'v1.31.1',
            'platform': 'linux/amd64',
            'compatibility_status': 'compatible',
            'compatibility_profile': 'kubernetes-core-v1',
            'readiness_status': 'ready',
            'lifecycle_status': 'current',
            'api_discovery_summary': {'features': {}},
            'validation_message': 'Validated',
        },
    )
    assert cluster.status == 'connected'
    assert cluster.node_count == 2
    assert connection.readiness_status == canonical.readiness_status == 'ready'
    assert connection.discovery_summary == {'features': {}}

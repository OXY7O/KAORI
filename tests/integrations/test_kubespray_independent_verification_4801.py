"""Independent Kubernetes API readback contract, using synthetic SDK responses."""

from dataclasses import replace
from types import SimpleNamespace as Obj

import pytest

from app.infrastructure_automation.kubernetes import verification as service

_CLUSTER = '00000000-0000-4000-8000-000000000001'
_NAMESPACE = '00000000-0000-4000-8000-000000000002'
_ORIGIN = 'https://cluster.fixture:6443'
_NODES = tuple(
    service.ExpectedPilotNode(
        f'00000000-0000-4000-8000-{index:012d}', f'node-{index}',
        f'10.0.0.{index}', 'control_plane' if index == 1 else 'worker',
    )
    for index in range(1, 4)
)
_INTENT = service.PilotVerificationIntent('a' * 64, _CLUSTER, _NAMESPACE, _NODES)


def _metadata(name, uid=None, **fields):
    return Obj(name=name, uid=uid, deletion_timestamp=None, **fields)


def _node(target, index):
    conditions = [Obj(type='Ready', status='True')]
    conditions.extend(Obj(type=kind, status='False') for kind in ('MemoryPressure', 'DiskPressure', 'PIDPressure'))
    return Obj(
        metadata=_metadata(
            target.name, f'00000000-0000-4000-8000-{index + 10:012d}',
            labels={'node-role.kubernetes.io/control-plane': ''} if target.role == 'control_plane' else {},
        ),
        status=Obj(addresses=[Obj(type='InternalIP', address=target.address)], conditions=conditions),
        spec=Obj(unschedulable=False),
    )


@pytest.fixture
def provider(monkeypatch):
    calls = []
    configuration = Obj(host=_ORIGIN, verify_ssl=True)
    api_client = Obj(
        configuration=configuration,
        call_api=lambda path, method, **kwargs: calls.append((method, path)) or 'ok',
        close=lambda: None,
    )
    namespace = Obj(metadata=_metadata('kube-system', _NAMESPACE))
    nodes = Obj(
        metadata=Obj(_continue=None),
        items=[_node(target, index) for index, target in enumerate(_NODES)],
    )
    def pod(name, namespace, **kwargs):
        return Obj(
            metadata=_metadata(name, namespace=namespace),
            spec=Obj(node_name='node-1'),
            status=Obj(
                phase='Running', conditions=[Obj(type='Ready', status='True')],
                container_statuses=[Obj(ready=True)],
            ),
        )
    core = Obj(
        api_client=api_client,
        read_namespace=lambda *args, **kwargs: namespace,
        list_node=lambda **kwargs: nodes,
        read_namespaced_pod=pod,
    )
    deployment = Obj(
        metadata=_metadata('coredns', namespace='kube-system', generation=2),
        spec=Obj(replicas=2),
        status=Obj(observed_generation=2, replicas=2, updated_replicas=2, ready_replicas=2, available_replicas=2),
    )
    apps = Obj(api_client=api_client, read_namespaced_deployment=lambda *args, **kwargs: deployment)
    version = Obj(api_client=api_client, get_code=lambda **kwargs: Obj(major='1', minor='36'))
    client = Obj(core_api=lambda: core, apps_api=lambda: apps, version_api=lambda: version)
    monkeypatch.setattr(service, 'get_integration', lambda key: Obj(execute=lambda *args: client))
    connection = Obj(
        cluster_id=_CLUSTER, cluster=Obj(environment='laboratory'), verify_ssl=True,
        allow_weak_tls=False, server=_ORIGIN,
    )
    return connection, core, nodes, namespace, deployment, api_client, calls


def test_independent_readback_remains_partial_not_run_acceptance(provider):
    connection, _, _, _, _, _, calls = provider
    result = service.observe_independent_pilot_api(connection, _INTENT)
    summary = result.committed_summary()
    assert summary['node_count'] == 3
    assert summary['api_etcd_ready'] is True
    assert summary['core_components_ready'] is True
    assert summary['dns_deployment_ready'] is True
    assert summary['etcd_quorum_verified'] is False
    assert summary['cni_cri_verified'] is False
    assert summary['provisioning_verified'] is False
    assert summary['mutation_authorized'] is False
    assert len(summary['node_identity_fingerprint']) == 64
    assert _ORIGIN not in str(summary)
    assert _NAMESPACE not in str(summary)
    assert calls == [('GET', '/readyz'), ('GET', '/readyz/etcd')] * 2


@pytest.mark.parametrize('drift', [
    'wrong_namespace', 'missing_node', 'extra_node', 'pagination', 'wrong_ip', 'not_ready',
    'wrong_role', 'duplicate_uid', 'pressure', 'dns', 'etcd', 'origin', 'tls', 'core_pod',
])
def test_wrong_or_unhealthy_api_observation_denies(provider, drift):
    connection, core, nodes, namespace, deployment, api, _ = provider
    if drift == 'wrong_namespace':
        namespace.metadata.uid = _CLUSTER
    elif drift == 'missing_node':
        nodes.items.pop()
    elif drift == 'extra_node':
        nodes.items.append(nodes.items[0])
    elif drift == 'pagination':
        nodes.metadata._continue = 'next'
    elif drift == 'wrong_ip':
        nodes.items[0].status.addresses[0].address = '10.0.0.99'
    elif drift == 'not_ready':
        nodes.items[0].status.conditions[0].status = 'False'
    elif drift == 'wrong_role':
        nodes.items[1].metadata.labels = {'node-role.kubernetes.io/control-plane': ''}
    elif drift == 'duplicate_uid':
        nodes.items[1].metadata.uid = nodes.items[0].metadata.uid
    elif drift == 'pressure':
        nodes.items[0].status.conditions[1].status = 'True'
    elif drift == 'dns':
        deployment.status.ready_replicas = 1
    elif drift == 'etcd':
        api.call_api = lambda path, *args, **kwargs: 'failed' if path == '/readyz/etcd' else 'ok'
    elif drift == 'origin':
        api.configuration.host = 'https://other.fixture'
    elif drift == 'tls':
        connection.verify_ssl = False
    else:
        original = core.read_namespaced_pod

        def unhealthy(*args, **kwargs):
            result = original(*args, **kwargs)
            result.status.phase = 'Failed'
            return result

        core.read_namespaced_pod = unhealthy
    with pytest.raises(service.PilotVerificationDenied):
        service.observe_independent_pilot_api(connection, _INTENT)


def test_provider_error_is_sanitized(provider):
    connection, core, *_ = provider

    def unavailable(*args, **kwargs):
        raise RuntimeError('fixture sensitive server response')

    core.list_node = unavailable
    with pytest.raises(service.PilotVerificationDenied) as caught:
        service.observe_independent_pilot_api(connection, _INTENT)
    assert 'sensitive' not in str(caught.value)


def test_cross_cluster_or_production_denied_before_provider(provider):
    connection, *_ = provider
    with pytest.raises(service.PilotVerificationDenied):
        service.observe_independent_pilot_api(connection, replace(_INTENT, cluster_id=_NAMESPACE))
    connection.cluster.environment = 'production'
    with pytest.raises(service.PilotVerificationDenied):
        service.observe_independent_pilot_api(connection, _INTENT)

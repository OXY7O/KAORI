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
        status=Obj(
            addresses=[Obj(type='InternalIP', address=target.address)], conditions=conditions,
            node_info=Obj(operating_system='linux', kubelet_version='v1.36.1', container_runtime_version='containerd://2.1.0'),
        ),
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
    dns_ports = [Obj(protocol='UDP', port=53), Obj(protocol='TCP', port=53)]
    service_uid = '00000000-0000-4000-8000-000000000020'
    dns_service = Obj(
        metadata=_metadata('kube-dns', service_uid, namespace='kube-system'),
        spec=Obj(type='ClusterIP', cluster_ip='10.96.0.10', ports=dns_ports),
    )
    endpoints = [
        Obj(
            conditions=Obj(ready=True, terminating=False, serving=True),
            target_ref=Obj(kind='Pod', namespace='kube-system', name=f'coredns-fixture-{index}',
                           uid=f'00000000-0000-4000-8000-{index + 30:012d}'),
            node_name=f'node-{index}', addresses=[f'10.244.0.{index}'],
        )
        for index in (1, 2)
    ]
    endpoint_slice = Obj(
        metadata=_metadata('kube-dns-fixture', '00000000-0000-4000-8000-000000000021',
                           namespace='kube-system', labels={'kubernetes.io/service-name': 'kube-dns'},
                           owner_references=[Obj(kind='Service', name='kube-dns', uid=service_uid)]),
        address_type='IPv4', ports=dns_ports, endpoints=endpoints,
    )
    slices = Obj(metadata=Obj(_continue=None), items=[endpoint_slice])
    core = Obj(
        api_client=api_client,
        read_namespace=lambda *args, **kwargs: namespace,
        list_node=lambda **kwargs: nodes,
        read_namespaced_pod=pod,
        read_namespaced_service=lambda *args, **kwargs: dns_service,
        fixture_service=dns_service,
        fixture_slices=slices,
    )
    deployment = Obj(
        metadata=_metadata('coredns', namespace='kube-system', generation=2),
        spec=Obj(replicas=2),
        status=Obj(observed_generation=2, replicas=2, updated_replicas=2, ready_replicas=2, available_replicas=2),
    )
    apps = Obj(api_client=api_client, read_namespaced_deployment=lambda *args, **kwargs: deployment)
    version = Obj(api_client=api_client, get_code=lambda **kwargs: Obj(major='1', minor='36'))
    discovery = Obj(api_client=api_client, list_namespaced_endpoint_slice=lambda *args, **kwargs: slices)
    client = Obj(core_api=lambda: core, apps_api=lambda: apps, version_api=lambda: version,
                 discovery_api=lambda: discovery)
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
    assert summary['node_kubelet_minor_verified'] is True
    assert summary['node_runtime_reported'] is True
    assert summary['dns_service_endpoints_ready'] is True
    assert len(summary['node_runtime_fingerprint']) == 64
    assert len(summary['dns_endpoint_fingerprint']) == 64
    assert 'containerd://' not in str(summary)
    assert '10.244.0.' not in str(summary)
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


@pytest.mark.parametrize('drift', [
    'kubelet', 'runtime', 'os', 'dns_service', 'dns_port', 'dns_owner',
    'dns_endpoint_not_ready', 'dns_endpoint_duplicate', 'dns_endpoint_wrong_node',
    'dns_endpoint_paginated', 'dns_endpoint_missing', 'runtime_second_read', 'dns_second_read',
])
def test_runtime_and_dns_endpoint_drift_denies(provider, drift):
    connection, core, nodes, _, _, _, _ = provider
    dns = core.fixture_service
    slices = core.fixture_slices
    first = slices.items[0]
    if drift == 'kubelet':
        nodes.items[0].status.node_info.kubelet_version = 'v1.35.1'
    elif drift == 'runtime':
        nodes.items[0].status.node_info.container_runtime_version = ''
    elif drift == 'os':
        nodes.items[0].status.node_info.operating_system = 'windows'
    elif drift == 'dns_service':
        dns.spec.cluster_ip = 'None'
    elif drift == 'dns_port':
        dns.spec.ports = [Obj(protocol='UDP', port=53)]
    elif drift == 'dns_owner':
        first.metadata.owner_references[0].uid = _CLUSTER
    elif drift == 'dns_endpoint_not_ready':
        first.endpoints[0].conditions.ready = False
    elif drift == 'dns_endpoint_duplicate':
        first.endpoints[1].target_ref.uid = first.endpoints[0].target_ref.uid
    elif drift == 'dns_endpoint_wrong_node':
        first.endpoints[0].node_name = 'foreign'
    elif drift == 'dns_endpoint_paginated':
        slices.metadata._continue = 'next'
    elif drift == 'dns_endpoint_missing':
        first.endpoints.pop()
    elif drift == 'runtime_second_read':
        reads = 0

        def list_nodes(**kwargs):
            nonlocal reads
            reads += 1
            if reads == 2:
                nodes.items[0].status.node_info.container_runtime_version = 'containerd://2.1.1'
            return nodes

        core.list_node = list_nodes
    else:
        reads = 0

        def read_service(*args, **kwargs):
            nonlocal reads
            reads += 1
            if reads == 2:
                first.endpoints[0].addresses = ['10.244.0.99']
            return dns

        core.read_namespaced_service = read_service
    with pytest.raises(service.PilotVerificationDenied):
        service.observe_independent_pilot_api(connection, _INTENT)

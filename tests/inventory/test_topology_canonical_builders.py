from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _topology_modules():
    for package in ('app', 'app.inventory', 'app.inventory.topology'):
        module = sys.modules.setdefault(package, ModuleType(package))
        module.__path__ = []
    contracts = _load_module(
        'app.inventory.topology.contracts',
        'app/inventory/topology/contracts.py',
    )
    presentation = _load_module(
        'app.inventory.topology.presentation',
        'app/inventory/topology/presentation.py',
    )
    return contracts, presentation


def test_topology_selection_is_derived_from_canonical_scope_and_depth() -> None:
    contracts, _ = _topology_modules()
    selection = contracts.TopologySelection.from_filters(scope='networking', depth='3')

    assert selection.include_level_1 is True
    assert selection.include_level_2 is True
    assert selection.include_pods is True
    assert selection.include_all_relationships is False
    assert selection.show_networking is True
    assert selection.show_compute is False


def test_topology_elements_use_structured_specs_instead_of_argument_wrappers() -> None:
    contracts, presentation = _topology_modules()
    collected_at = datetime(2026, 8, 5, 7, 0, tzinfo=UTC)
    node = presentation.node_element(
        contracts.TopologyNodeSpec(
            element_id='pod:1',
            label='api-1',
            resource_type='pod',
            kind='Pod',
            status='Running',
            status_tone='healthy',
            cluster_id='cluster-1',
            cluster_name='Production',
            namespace='payments',
            parent='namespace:1',
            fields=[{'label': 'Phase', 'value': 'Running'}],
            collected_at=collected_at,
            action_url='/inventory/pods/1',
            description='Pod evidence.',
        )
    )
    edge = presentation.edge_element(
        contracts.TopologyEdgeSpec(
            edge_id='owns:1',
            source='workload:1',
            target='pod:1',
            relationship='owns',
            label='owns',
            source_label='api',
            target_label='api-1',
            description='Ownership evidence.',
        )
    )

    assert node['data']['parent'] == 'namespace:1'
    assert node['data']['collected_at'] == collected_at.isoformat()
    assert edge['data']['relationship'] == 'owns'


def test_topology_limit_keeps_parent_nodes_and_filters_dangling_edges() -> None:
    _, presentation = _topology_modules()
    nodes = [
        {'data': {'id': 'cluster:1', 'type': 'cluster'}},
        {'data': {'id': 'namespace:1', 'type': 'namespace'}},
        {'data': {'id': 'pod:1', 'type': 'pod'}},
        {'data': {'id': 'pod:2', 'type': 'pod'}},
    ]
    edges = [
        {'data': {'source': 'namespace:1', 'target': 'pod:1'}},
        {'data': {'source': 'namespace:1', 'target': 'pod:2'}},
    ]

    limited_nodes, limited_edges, omitted, omitted_by_type = presentation.limit_graph(nodes, edges, 3)

    assert [node['data']['id'] for node in limited_nodes[:2]] == ['cluster:1', 'namespace:1']
    assert len(limited_edges) == 1
    assert omitted == 1
    assert omitted_by_type == {'pod': 1}


def _topology_builder_modules():
    contracts, presentation = _topology_modules()

    flask = ModuleType('flask')
    flask.url_for = lambda endpoint, **values: f"/{endpoint}?" + '&'.join(
        f'{key}={value}' for key, value in sorted(values.items())
    )
    sys.modules['flask'] = flask

    for package in (
        'app.cluster',
        'app.integrations',
        'app.integrations.kubernetes',
        'app.inventory.resources',
    ):
        module = sys.modules.setdefault(package, ModuleType(package))
        module.__path__ = []

    constants = ModuleType('app.cluster.constants')
    constants.get_environment_label = lambda value: str(value or 'Not Reported').title()
    sys.modules['app.cluster.constants'] = constants

    resolver = ModuleType('app.integrations.kubernetes.resolver')
    resolver.server_for_cluster = lambda cluster: getattr(cluster, 'server', None)
    sys.modules['app.integrations.kubernetes.resolver'] = resolver

    _load_module(
        'app.inventory.formatting',
        'app/inventory/formatting.py',
    )
    _load_module(
        'app.inventory.resources.ingress_semantics',
        'app/inventory/resources/ingress_semantics.py',
    )
    _load_module(
        'app.inventory.resources.storage_semantics',
        'app/inventory/resources/storage_semantics.py',
    )

    node_builder = _load_module(
        'app.inventory.topology.node_builder',
        'app/inventory/topology/node_builder.py',
    )
    edge_builder = _load_module(
        'app.inventory.topology.edge_builder',
        'app/inventory/topology/edge_builder.py',
    )
    graph_builder = _load_module(
        'app.inventory.topology.graph_builder',
        'app/inventory/topology/graph_builder.py',
    )
    return contracts, presentation, node_builder, edge_builder, graph_builder


def test_topology_builder_preserves_canonical_nodes_and_relationships() -> None:
    from types import SimpleNamespace

    contracts, _, _, _, graph_builder = _topology_builder_modules()
    collected = datetime(2026, 8, 5, 8, 0, tzinfo=UTC)
    cluster = SimpleNamespace(
        id='cluster-1',
        name='Production',
        status='connected',
        environment='production',
        node_count=1,
        updated_at=collected,
        server='https://kubernetes.example',
    )
    namespace = SimpleNamespace(
        id=1,
        cluster_id='cluster-1',
        namespace='payments',
        status='Active',
        uid='namespace-uid',
        limit_range_count=1,
        network_policy_count=1,
        service_account_count=2,
        collected_at=collected,
    )
    node = SimpleNamespace(
        id=2,
        cluster_id='cluster-1',
        node_name='worker-1',
        role='Worker',
        status='Ready',
        internal_ip='10.0.0.10',
        os_image='Linux',
        kubelet_version='v1.29.5',
        collected_at=collected,
    )
    workload = SimpleNamespace(
        id=3,
        cluster_id='cluster-1',
        namespace='payments',
        workload_type='Deployment',
        name='api',
        status='Stable',
        ready='1/1',
        collected_at=collected,
    )
    service = SimpleNamespace(
        id=4,
        cluster_id='cluster-1',
        namespace='payments',
        service_name='api',
        service_type='ClusterIP',
        cluster_ip='10.96.0.10',
        selector={'app': 'api'},
        details={
            'external_addresses': [],
            'ports': [{'port': 443, 'protocol': 'TCP'}],
        },
        collected_at=collected,
    )
    ingress = SimpleNamespace(
        id=5,
        cluster_id='cluster-1',
        namespace='payments',
        ingress_name='api',
        backend_paths=[{'service_name': 'api', 'service_port': 443, 'path': '/'}],
        host='api.example.com',
        ingress_class='nginx',
        tls_enabled=True,
        details={
            'specification_evidence_reported': True,
            'ingress_class_source': 'spec.ingressClassName',
            'hosts': ['api.example.com'],
            'hostless_rule_count': 0,
            'publication_evidence_reported': True,
            'addresses': ['10.0.0.20'],
        },
        collected_at=collected,
    )
    configuration = SimpleNamespace(
        id=6,
        cluster_id='cluster-1',
        namespace='payments',
        object_type='ConfigMap',
        name='api-config',
        immutable=False,
        secret_type=None,
        key_count=2,
        payload_size_bytes=128,
        collected_at=collected,
    )
    pvc = SimpleNamespace(
        id=7,
        cluster_id='cluster-1',
        namespace='payments',
        storage_type='PersistentVolumeClaim',
        name='api-data',
        status='Bound',
        storage_class='fast',
        capacity='10Gi',
        details={
            'specification_evidence_reported': True,
            'status_evidence_reported': True,
            'capacity_evidence_reported': True,
            'volume_name': 'pv-api',
            'requested_storage': '10Gi',
        },
        collected_at=collected,
    )
    pv = SimpleNamespace(
        id=8,
        cluster_id='cluster-1',
        namespace=None,
        storage_type='PersistentVolume',
        name='pv-api',
        status='Bound',
        storage_class='fast',
        capacity='10Gi',
        details={
            'specification_evidence_reported': True,
            'status_evidence_reported': True,
            'claim_namespace': 'payments',
            'claim_name': 'api-data',
        },
        collected_at=collected,
    )
    pod = SimpleNamespace(
        id=9,
        cluster_id='cluster-1',
        namespace='payments',
        pod_name='api-abc',
        phase='Running',
        ready='1/1',
        workload_type='Deployment',
        workload_name='api',
        node_name='worker-1',
        pod_ip='10.244.0.10',
        restart_count=0,
        labels={'app': 'api'},
        configuration_references=[{'type': 'ConfigMap', 'name': 'api-config'}],
        persistent_volume_claims=['api-data'],
        collected_at=collected,
    )
    orphan_ingress = SimpleNamespace(
        id=10,
        cluster_id='cluster-1',
        namespace='missing',
        ingress_name='orphan',
        backend_paths=[{'service_name': 'api', 'service_port': 443, 'path': '/orphan'}],
        host='orphan.example.com',
        ingress_class='nginx',
        tls_enabled=False,
        details={
            'specification_evidence_reported': True,
            'ingress_class_source': 'spec.ingressClassName',
            'hosts': ['orphan.example.com'],
            'hostless_rule_count': 0,
            'publication_evidence_reported': True,
            'addresses': ['10.0.0.30'],
        },
        collected_at=collected,
    )
    records = contracts.TopologyRecords(
        clusters=[cluster],
        cluster_by_id={'cluster-1': cluster},
        latest_cluster_inventory={
            'cluster-1': SimpleNamespace(kubernetes_version='v1.29.5', collected_at=collected)
        },
        namespaces=[namespace],
        nodes=[node],
        workloads=[workload],
        services=[service],
        ingresses=[ingress, orphan_ingress],
        configurations=[configuration],
        storage_items=[pvc, pv],
        pods=[pod],
    )
    selection = contracts.TopologySelection.from_filters(scope='all', depth='full')

    payload = graph_builder.TopologyGraphBuilder(records, selection, max_nodes=350).build(
        filters={'cluster_id': 'cluster-1', 'namespace': 'payments', 'scope': 'all', 'depth': 'full'},
        scope_label='All Resources',
        depth_label='Full Relationships',
    )

    node_types = {node['data']['type'] for node in payload['nodes']}
    relationships = {edge['data']['relationship'] for edge in payload['edges']}
    node_ids = {node['data']['id'] for node in payload['nodes']}
    assert all(
        edge['data']['source'] in node_ids and edge['data']['target'] in node_ids
        for edge in payload['edges']
    )
    assert node_types == {
        'cluster',
        'namespace',
        'node',
        'workload',
        'service',
        'ingress',
        'configmap',
        'pvc',
        'pv',
        'pod',
    }
    assert relationships == {
        'owns',
        'scheduled_on',
        'routes_to',
        'selects',
        'uses',
        'binds',
        'mounts',
    }
    assert payload['summary']['last_collected_at'] == collected.isoformat()


def test_topology_limit_never_exceeds_maximum_when_many_resource_groups_compete() -> None:
    _, presentation = _topology_modules()
    nodes = [
        {'data': {'id': f'namespace:{index}', 'type': 'namespace'}}
        for index in range(349)
    ]
    nodes.extend(
        {'data': {'id': f'{resource_type}:1', 'type': resource_type}}
        for resource_type in ('node', 'workload', 'service', 'ingress', 'configmap', 'secret', 'pvc', 'pv', 'pod')
    )

    limited_nodes, _, omitted, omitted_by_type = presentation.limit_graph(nodes, [], 350)

    assert len(limited_nodes) == 350
    assert omitted == 8
    assert sum(omitted_by_type.values()) == 8

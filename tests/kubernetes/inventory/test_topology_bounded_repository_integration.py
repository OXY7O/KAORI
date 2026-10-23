from __future__ import annotations

from datetime import UTC, datetime

import pytest
from flask import Flask

from app.extensions.db import db
from app.kubernetes.inventory.topology.contracts import TopologySelection
from app.kubernetes.inventory.topology.repository import _storage_for_namespace, load_topology_records
from app.models import (
    Cluster,
    ClusterInventory,
    ConfigurationInventory,
    IngressInventory,
    NamespaceInventory,
    NodeInventory,
    PodInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)

MODELS = (
    Cluster,
    ClusterInventory,
    NamespaceInventory,
    NodeInventory,
    WorkloadInventory,
    PodInventory,
    ServiceInventory,
    IngressInventory,
    StorageInventory,
    ConfigurationInventory,
)


@pytest.fixture()
def repository_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite+pysqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        for model in MODELS:
            model.__table__.create(db.engine)
        yield app
        db.session.remove()
        for model in reversed(MODELS):
            model.__table__.drop(db.engine)


def test_deep_candidate_prefixes_preserve_full_committed_type_counts(repository_app, monkeypatch) -> None:
    now = datetime.now(UTC)
    with repository_app.app_context():
        cluster = Cluster(id='cluster-a', name='A', environment='production', status='connected')
        snapshot = ClusterInventory(cluster_id=cluster.id, collected_at=now)
        db.session.add_all(
            [
                cluster,
                snapshot,
                NamespaceInventory(cluster_id=cluster.id, namespace='app', collected_at=now),
                NodeInventory(cluster_id=cluster.id, node_name='worker', collected_at=now),
            ]
        )
        for index in range(355):
            name = f'resource-{index:04d}'
            db.session.add_all(
                [
                    WorkloadInventory(
                        cluster_id=cluster.id,
                        namespace='app',
                        name=name,
                        workload_type='Deployment',
                        collected_at=now,
                    ),
                    ServiceInventory(
                        cluster_id=cluster.id,
                        namespace='app',
                        service_name=name,
                        # A Pod selected by a Service beyond the 350 visible prefix
                        # must remain present in deep Networking graph projections.
                        selector={'app': 'late'} if index == 354 else {},
                        collected_at=now,
                    ),
                    IngressInventory(cluster_id=cluster.id, namespace='app', ingress_name=name, collected_at=now),
                    ConfigurationInventory(
                        cluster_id=cluster.id,
                        namespace='app',
                        name=name,
                        object_type='ConfigMap',
                        collected_at=now,
                    ),
                    ConfigurationInventory(
                        cluster_id=cluster.id,
                        namespace='app',
                        name=name,
                        object_type='Secret',
                        collected_at=now,
                    ),
                    StorageInventory(
                        cluster_id=cluster.id,
                        namespace='app',
                        name=name,
                        storage_type='PersistentVolumeClaim',
                        details={'volume_name': f'pv-{index:04d}'},
                        collected_at=now,
                    ),
                    StorageInventory(
                        cluster_id=cluster.id,
                        namespace=None,
                        name=f'pv-{index:04d}',
                        storage_type='PersistentVolume',
                        collected_at=now,
                    ),
                    PodInventory(
                        cluster_id=cluster.id,
                        namespace='app',
                        pod_name=name,
                        node_name='worker',
                        workload_type='Deployment',
                        workload_name=name,
                        labels={'app': 'late'} if index == 354 else {},
                        collected_at=now,
                    ),
                ]
            )
        db.session.add(
            WorkloadInventory(
                cluster_id=cluster.id,
                namespace='orphan',
                name='orphan',
                workload_type='Deployment',
                collected_at=now,
            )
        )
        db.session.commit()

        full = load_topology_records(
            clusters=[cluster],
            latest_inventory={cluster.id: snapshot},
            namespace='',
            selection=TopologySelection.from_filters(scope='all', depth='full'),
            max_nodes=350,
        )
        for kind, records in (
            ('workload', full.workloads),
            ('service', full.services),
            ('ingress', full.ingresses),
            ('pod', full.pods),
        ):
            assert full.source_totals[kind] == 355
            assert len(records) == 350
        assert full.source_totals['configmap'] == 355
        assert full.source_totals['secret'] == 355
        assert len(full.configurations) == 700
        assert full.source_totals['pvc'] == 355
        assert full.source_totals['pv'] == 355
        assert len(full.storage_items) == 700
        assert full.source_totals['namespace'] == 1
        assert len(full.nodes) == 1

        networking = load_topology_records(
            clusters=[cluster],
            latest_inventory={cluster.id: snapshot},
            namespace='',
            selection=TopologySelection.from_filters(scope='networking', depth='3'),
            max_nodes=350,
        )
        # All selectors remain available for deep Networking Pod relevance.
        assert len(networking.services) == 355
        assert 'service' not in networking.source_totals
        assert len(networking.pods) == 355
        assert 'pod' not in networking.source_totals
        assert any(service.selector.get('app') == 'late' for service in networking.services)

        scoped = load_topology_records(
            clusters=[cluster],
            latest_inventory={cluster.id: snapshot},
            namespace='app',
            selection=TopologySelection.from_filters(scope='all', depth='full'),
            max_nodes=350,
        )
        assert len(scoped.nodes) == 1
        assert len(scoped.storage_items) == 700
        assert scoped.source_totals['pvc'] == 355
        assert scoped.source_totals['pv'] == 355

        # Graph parity, not merely an ORM row-count contract: the candidate
        # budget must preserve all rendered nodes, edges and omission evidence.
        from types import SimpleNamespace

        from app.kubernetes.inventory.topology import node_builder
        from app.kubernetes.inventory.topology.graph_builder import TopologyGraphBuilder

        monkeypatch.setattr(node_builder, 'url_for', lambda endpoint, **kwargs: f'/{endpoint}')
        display_cluster = SimpleNamespace(
            id=cluster.id,
            name=cluster.name,
            status=cluster.status,
            environment=cluster.environment,
            node_count=1,
            updated_at=now,
            kubernetes_connection=None,
        )

        cases = (
            ('all', 'full', ''),
            ('compute', '3', ''),
            ('networking', '3', ''),
            ('all', 'full', 'app'),
            ('storage', 'full', 'app'),
        )
        for scope, depth, namespace in cases:
            selection = TopologySelection.from_filters(scope=scope, depth=depth)
            arguments = dict(
                clusters=[display_cluster],
                latest_inventory={cluster.id: snapshot},
                namespace=namespace,
                selection=selection,
            )
            bounded = load_topology_records(**arguments, max_nodes=350)
            complete = load_topology_records(**arguments, max_nodes=None)
            filters = {'cluster_id': cluster.id, 'namespace': namespace, 'scope': scope, 'depth': depth}
            builder_args = dict(
                filters=filters,
                scope_label='Test scope',
                depth_label='Test depth',
            )
            bounded_graph = TopologyGraphBuilder(bounded, selection, max_nodes=350).build(**builder_args)
            complete_graph = TopologyGraphBuilder(complete, selection, max_nodes=350).build(**builder_args)

            assert [row['data']['id'] for row in bounded_graph['nodes']] == [
                row['data']['id'] for row in complete_graph['nodes']
            ], (scope, depth, namespace)
            assert [row['data'] for row in bounded_graph['edges']] == [
                row['data'] for row in complete_graph['edges']
            ], (scope, depth, namespace)
            assert bounded_graph['summary'] == complete_graph['summary'], (
                scope,
                depth,
                namespace,
            )
            assert bounded_graph['type_counts'] == complete_graph['type_counts']


def test_namespace_pv_bindings_do_not_cross_cluster_boundaries(repository_app) -> None:
    now = datetime.now(UTC)
    with repository_app.app_context():
        claim = StorageInventory(
            cluster_id='a',
            namespace='app',
            name='claim',
            storage_type='PersistentVolumeClaim',
            details={'volume_name': 'pv-shared'},
            collected_at=now,
        )
        owned_volume = StorageInventory(
            cluster_id='a',
            namespace=None,
            name='pv-shared',
            storage_type='PersistentVolume',
            collected_at=now,
        )
        other_volume = StorageInventory(
            cluster_id='b',
            namespace=None,
            name='pv-shared',
            storage_type='PersistentVolume',
            collected_at=now,
        )
        assert _storage_for_namespace([claim, owned_volume, other_volume], 'app') == [claim, owned_volume]

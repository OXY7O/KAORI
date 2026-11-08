from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask

from app.extensions.db import db
from app.kubernetes.inventory.overview import (
    get_inventory_overview,
    get_inventory_overview_cluster_detail,
)
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
def overview_app():
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


def test_overview_sql_paging_preserves_fleet_totals_signals_and_scoped_detail(overview_app) -> None:
    now = datetime.now(UTC)
    with overview_app.app_context():
        for index in range(7):
            cluster_id = f'cluster-{index:02d}'
            db.session.add(
                Cluster(
                    id=cluster_id,
                    name=f'Cluster {index}',
                    status='connected',
                    environment='production',
                    created_at=now + timedelta(seconds=index),
                )
            )
            if index == 2:
                continue  # Never synchronized; must not silently count as Healthy.
            evidence = (
                {'inventory.pods': 'Collected', 'inventory.services': 'Not Reported'}
                if index == 1
                else {'inventory.pods': 'Collected', 'inventory.services': 'Collected'}
            )
            db.session.add(
                ClusterInventory(
                    cluster_id=cluster_id,
                    collected_at=now,
                    collection_evidence=evidence,
                )
            )

        for index in (0, 6):
            db.session.add(
                NodeInventory(
                    cluster_id=f'cluster-{index:02d}',
                    node_name='worker-current',
                    collected_at=now,
                )
            )
        db.session.add(
            NodeInventory(
                cluster_id='cluster-06',
                node_name='obsolete-generation',
                collected_at=now - timedelta(days=1),
            )
        )
        db.session.commit()

        page_one = get_inventory_overview(cluster_page=1, cluster_per_page=5)
        page_two = get_inventory_overview(cluster_page=2, cluster_per_page=5)
        oversized = get_inventory_overview(cluster_page=1, cluster_per_page=5000)

        assert page_one['resources_pagination']['total_items'] == 7
        assert page_one['resources_pagination']['per_page'] == 5
        assert [row['id'] for row in page_one['clusters']] == [f'cluster-{index:02d}' for index in range(5)]
        assert page_two['resources_pagination']['page'] == 2
        assert [row['id'] for row in page_two['clusters']] == ['cluster-05', 'cluster-06']
        assert oversized['resources_pagination']['per_page'] == 5
        assert len(oversized['clusters']) == 5

        assert page_one['total_clusters'] == page_two['total_clusters'] == 7
        assert page_one['total_nodes'] == page_two['total_nodes'] == 2
        assert page_one['inventory_total'] == page_two['inventory_total'] == 2
        assert page_one['active_signal_count'] == page_two['active_signal_count']
        assert page_one['active_signal_count'] > sum(len(row['signals']) for row in page_two['clusters'])
        assert page_one['posture']['status'] == 'Attention'

        partial = page_one['clusters'][1]
        missing = page_one['clusters'][2]
        assert any(signal['label'] == 'Collection Incomplete' for signal in partial['signals'])
        assert any(signal['label'] == 'Never Collected' for signal in missing['signals'])

        detail = get_inventory_overview_cluster_detail('cluster-06')
        assert detail is not None
        assert detail['counts']['nodes'] == 1
        assert detail['id'] == 'cluster-06'
        assert get_inventory_overview_cluster_detail('does-not-exist') is None

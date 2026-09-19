from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask

from app.extensions.db import db
from app.kubernetes.inventory.resources.nodes import get_node_inventory
from app.models import Cluster, ClusterInventory, NodeInventory


@pytest.fixture()
def inventory_repository_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite+pysqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        Cluster.__table__.create(db.engine)
        ClusterInventory.__table__.create(db.engine)
        NodeInventory.__table__.create(db.engine)
        yield app
        db.session.remove()
        NodeInventory.__table__.drop(db.engine)
        ClusterInventory.__table__.drop(db.engine)
        Cluster.__table__.drop(db.engine)


def test_node_inventory_reads_only_committed_generation_and_enforces_canonical_page_size(
    inventory_repository_app,
) -> None:
    now = datetime.now(UTC)
    with inventory_repository_app.app_context():
        cluster = Cluster(id='cluster-a', name='Cluster A', environment='production', status='connected')
        db.session.add(cluster)
        db.session.add(ClusterInventory(cluster_id=cluster.id, kubernetes_version='v1.29.5', collected_at=now))
        db.session.add(
            NodeInventory(
                cluster_id=cluster.id,
                node_name='old-generation-node',
                status='Ready',
                role='worker',
                collected_at=now - timedelta(hours=1),
            )
        )
        for index in range(7):
            db.session.add(
                NodeInventory(
                    cluster_id=cluster.id,
                    node_name=f'worker-{index}',
                    status='Ready',
                    role='worker',
                    cpu=4,
                    memory='8Gi',
                    ephemeral_storage='20Gi',
                    collected_at=now,
                )
            )
        db.session.commit()

        page_two = get_node_inventory(cluster_id=cluster.id, page=2, per_page=5)
        oversized = get_node_inventory(cluster_id=cluster.id, page=1, per_page=5000)

        assert page_two['pagination']['total_items'] == 7
        assert page_two['pagination']['per_page'] == 5
        assert [row['node_name'] for row in page_two['nodes']] == ['worker-5', 'worker-6']
        assert oversized['pagination']['per_page'] == 5
        assert len(oversized['nodes']) == 5
        assert all(row['node_name'] != 'old-generation-node' for row in oversized['nodes'])

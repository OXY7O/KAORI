from __future__ import annotations

from flask import Flask

from app.analytics.kubernetes.materialization.service import read_snapshot, store_snapshot
from app.extensions.db import db
from app.models import AnalyticsSnapshot, Cluster


def test_materialized_snapshot_round_trip_uses_canonical_scope_identity() -> None:
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)

    with app.app_context():
        Cluster.__table__.create(db.engine)
        AnalyticsSnapshot.__table__.create(db.engine)
        cluster = Cluster(id='cluster-analytics', name='Analytics Cluster', environment='test')
        db.session.add(cluster)
        db.session.commit()

        store_snapshot(
            cluster_id=cluster.id,
            dataset_key='analytics.capacity',
            parameters={'time_range': '24h'},
            context={'available': True, 'marker': 'committed'},
            job_execution_id=None,
            freshness_minutes=20,
        )
        result = read_snapshot(
            cluster_id=cluster.id,
            dataset_key='analytics.capacity',
            parameters={'time_range': '24h'},
        )

        assert result.available is True
        assert result.state == 'fresh'
        assert result.context == {'available': True, 'marker': 'committed'}

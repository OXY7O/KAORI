from __future__ import annotations

from flask import Flask

from app.extensions.db import db
from app.kubernetes.analytics.materialization.service import read_snapshot, store_snapshot
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


def test_failed_and_pending_generation_never_reuses_fresh_payload_as_ready() -> None:
    from app.kubernetes.analytics.materialization.service import (
        fail_snapshot,
        mark_snapshot_pending,
        read_last_known_snapshot,
        read_snapshots,
    )

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)

    with app.app_context():
        Cluster.__table__.create(db.engine)
        AnalyticsSnapshot.__table__.create(db.engine)
        cluster = Cluster(id='cluster-lifecycle', name='Lifecycle Cluster', environment='test')
        db.session.add(cluster)
        db.session.commit()
        parameters = {'time_range': '24h'}

        store_snapshot(
            cluster_id=cluster.id,
            dataset_key='analytics.capacity',
            parameters=parameters,
            context={'available': True, 'marker': 'last-success'},
            job_execution_id=None,
            freshness_minutes=20,
        )
        ready = read_snapshot(cluster_id=cluster.id, dataset_key='analytics.capacity', parameters=parameters)
        assert ready.state == 'fresh'
        assert ready.available

        mark_snapshot_pending(
            cluster_id=cluster.id, dataset_key='analytics.capacity',
            parameters=parameters, job_execution_id=None,
        )
        pending = read_snapshot(cluster_id=cluster.id, dataset_key='analytics.capacity', parameters=parameters)
        assert pending.state == 'pending'
        assert not pending.available
        assert pending.context is None
        old = read_last_known_snapshot(
            cluster_id=cluster.id, dataset_key='analytics.capacity', parameters=parameters,
        )
        assert old.state == 'refreshing'
        assert old.context == {'available': True, 'marker': 'last-success'}

        fail_snapshot(
            cluster_id=cluster.id, dataset_key='analytics.capacity',
            parameters=parameters, error='Test provider unavailable', job_execution_id=None,
        )
        failed = read_snapshot(cluster_id=cluster.id, dataset_key='analytics.capacity', parameters=parameters)
        assert failed.state == 'failed'
        assert not failed.available
        assert read_last_known_snapshot(
            cluster_id=cluster.id, dataset_key='analytics.capacity', parameters=parameters,
        ).state == 'failed'
        batch = read_snapshots(
            dataset_key='analytics.capacity',
            parameters_by_cluster={cluster.id: parameters},
        )
        assert batch[cluster.id].state == 'failed'
        assert not batch[cluster.id].available

        store_snapshot(
            cluster_id=cluster.id,
            dataset_key='analytics.capacity',
            parameters=parameters,
            context={'available': True, 'marker': 'new-success'},
            job_execution_id=None,
        )
        repaired = read_snapshot(cluster_id=cluster.id, dataset_key='analytics.capacity', parameters=parameters)
        assert repaired.available
        assert repaired.state == 'fresh'
        assert repaired.context['marker'] == 'new-success'

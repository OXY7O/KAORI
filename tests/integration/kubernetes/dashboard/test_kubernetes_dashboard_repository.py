from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask

from app.extensions.db import db
from app.kubernetes.dashboard import repository


class DashboardIntegrationRecord(db.Model):
    __tablename__ = 'dashboard_integration_record'

    id = db.Column(db.Integer, primary_key=True)
    cluster_id = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)


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
        DashboardIntegrationRecord.__table__.create(db.engine)
        yield app
        db.session.remove()
        DashboardIntegrationRecord.__table__.drop(db.engine)


def test_dashboard_repository_filters_counts_orders_and_reads_latest_timestamp(repository_app) -> None:
    now = datetime.now(UTC)
    with repository_app.app_context():
        db.session.add_all(
            [
                DashboardIntegrationRecord(cluster_id='a', name='older', created_at=now - timedelta(minutes=2)),
                DashboardIntegrationRecord(cluster_id='a', name='newer', created_at=now - timedelta(minutes=1)),
                DashboardIntegrationRecord(cluster_id='b', name='other', created_at=now),
            ]
        )
        db.session.commit()

        rows = repository.query_all(DashboardIntegrationRecord, cluster_id='a')

        assert [row.name for row in rows] == ['newer', 'older']
        assert repository.count_records(DashboardIntegrationRecord, 'a') == 2
        latest = repository.latest_record_timestamp(DashboardIntegrationRecord, 'a')
        assert latest is not None
        assert latest.replace(tzinfo=UTC) == (now - timedelta(minutes=1)).replace(tzinfo=UTC)

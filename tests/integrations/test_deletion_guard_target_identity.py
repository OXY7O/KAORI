from __future__ import annotations

import pytest
from flask import Flask

from app.extensions import db
from app.integrations.deletion import (
    kubernetes_active_job_count,
    provider_active_job_count,
)
from app.models.job import JobExecution

pytestmark = pytest.mark.functional


@pytest.fixture()
def app() -> Flask:
    application = Flask(__name__)
    application.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(application)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _job(*, resource_group: str, status: str = 'queued') -> JobExecution:
    job = JobExecution(
        job_type='integration_operation',
        operation='runtime_refresh',
        workload_class='runtime',
        queue_name='validation',
        status=status,
        deduplication_key=f'{resource_group}:{status}',
        active_deduplication_key=f'{resource_group}:{status}' if status == 'queued' else None,
        parameter_fingerprint='0' * 64,
        resource_group=resource_group,
    )
    db.session.add(job)
    db.session.commit()
    return job


def test_provider_guard_detects_active_job_from_resource_group(app: Flask) -> None:
    with app.app_context():
        _job(resource_group='integration:prometheus:41')

        assert provider_active_job_count(
            provider_type='prometheus',
            provider_instance_id=41,
        ) == 1


def test_provider_guard_ignores_terminal_resource_group_job(app: Flask) -> None:
    with app.app_context():
        _job(resource_group='integration:alertmanager:12', status='succeeded')

        assert provider_active_job_count(
            provider_type='alertmanager',
            provider_instance_id=12,
        ) == 0


def test_kubernetes_guard_detects_cluster_resource_group(app: Flask) -> None:
    with app.app_context():
        _job(resource_group='kubernetes-cluster:cluster-a')

        assert kubernetes_active_job_count(
            connection_id=7,
            cluster_id='cluster-a',
        ) == 1


def test_kubernetes_guard_detects_connection_resource_group(app: Flask) -> None:
    with app.app_context():
        _job(resource_group='integration:kubernetes:7')

        assert kubernetes_active_job_count(
            connection_id=7,
            cluster_id='cluster-a',
        ) == 1

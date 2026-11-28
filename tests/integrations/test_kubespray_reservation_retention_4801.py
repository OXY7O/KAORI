"""Reservation history must survive canonical JobExecution retention (#4801)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, select
from sqlalchemy.orm import Session

from app.models.automation import AutomationRunTargetClaim
from app.models.job import JobExecution
from app.platform_operations.data_lifecycle.retention.domains import job_execution as retention


@pytest.fixture
def retention_session(monkeypatch):
    metadata = MetaData()
    Table('users', metadata, Column('id', Integer, primary_key=True))
    Table('integration_instances', metadata, Column('id', Integer, primary_key=True))
    jobs = JobExecution.__table__.to_metadata(metadata)
    claims = AutomationRunTargetClaim.__table__.to_metadata(metadata)
    engine = create_engine('sqlite://')
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
            metadata.create_all(connection)
            connection.execute(insert(metadata.tables['users']), {'id': 7})
            for job_id in range(1, 9):
                connection.execute(insert(jobs), {
                    'id': job_id,
                    'parent_job_id': job_id - 4 if job_id > 4 else None,
                    'job_type': 'fixture',
                    'operation': 'fixture',
                    'queue_name': 'fixture',
                    'status': 'succeeded',
                    'deduplication_key': f'fixture-{job_id}',
                    'parameter_fingerprint': 'a' * 64,
                    'completed_at': datetime.now(UTC) - timedelta(days=120),
                })
        with Session(engine) as session:
            monkeypatch.setattr(retention, 'db', SimpleNamespace(session=session))
            yield session, claims
    finally:
        engine.dispose()


def _reserve(session, claims, job_id, *, released=False):
    now = datetime.now(UTC)
    key = f'kubespray:connection:{job_id}'
    session.execute(insert(claims), {
        'reservation_id': str(uuid4()),
        'plan_job_id': job_id,
        'resource_key': key,
        'active_resource_key': None if released else key,
        'plan_fingerprint': 'a' * 64,
        'reserved_by_user_id': 7,
        'reserved_at': now,
        'released_at': now if released else None,
    })
    session.commit()


def test_retention_preserves_active_released_and_late_claims(retention_session):
    session, claims = retention_session
    _reserve(session, claims, 1)
    _reserve(session, claims, 2, released=True)
    policy = retention.RetentionPolicy(
        domain='job_execution',
        enabled=True,
        retention_days=90,
        archive_retention_days=365,
        batch_size=100,
        settings={},
    )
    domain = retention.JobExecutionArchiveDomain()
    eligible = domain._eligible_filter(policy, now=datetime.now(UTC))
    selected = list(session.scalars(select(JobExecution.id).where(eligible).order_by(JobExecution.id)))
    assert selected == [3, 4, 7, 8]

    # A reservation committed after archive selection protects both rows.
    _reserve(session, claims, 3)
    assert domain.cleanup_records([1, 2, 5, 6, *selected], policy) == 2
    assert list(session.scalars(select(JobExecution.id).order_by(JobExecution.id))) == [1, 2, 3, 5, 6, 7]
    assert list(session.scalars(select(claims.c.plan_job_id).order_by(claims.c.plan_job_id))) == [1, 2, 3]


def test_child_only_cleanup_does_not_delete_lock_only_parent(retention_session):
    session, _ = retention_session
    assert retention.JobExecutionArchiveDomain._delete_id_batch([8]) == 1
    assert session.get(JobExecution, 4) is not None
    assert session.get(JobExecution, 8) is None

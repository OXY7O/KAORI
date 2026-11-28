"""Canonical job staging shares one transaction with domain admission evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from flask import Flask
from sqlalchemy import Column, Integer, MetaData, Table, insert
from app.extensions.db import db
from app.models.audit import AuditEvent
from app.models.job import JobExecution, JobExecutionSubscriber
from app.platform_operations.jobs import service


@pytest.fixture
def requester_id():
    # The transaction contract does not need a configured application database.
    # Never create/drop the full schema from a test fixture.
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    db.init_app(app)
    metadata = MetaData()
    users = Table('users', metadata, Column('id', Integer, primary_key=True))
    Table('integration_instances', metadata, Column('id', Integer, primary_key=True))
    for model in (JobExecution, JobExecutionSubscriber, AuditEvent):
        model.__table__.to_metadata(metadata)
    with app.app_context():
        try:
            with db.engine.begin() as connection:
                connection.exec_driver_sql('PRAGMA foreign_keys=ON')
                metadata.create_all(connection)
                connection.execute(insert(users), [{'id': 7}, {'id': 8}])
            yield 7
        finally:
            db.session.rollback()
            db.session.remove()
            db.engine.dispose()


def _spec(requester_id, **overrides):
    return replace(
        service.JobCreationSpec(
            job_type='fixture',
            operation='fixture_parent',
            queue_name='automation',
            workload_class='validation',
            requested_by_user_id=requester_id,
            parameters={'fixture': 'parent'},
            max_attempts=1,
        ),
        **overrides,
    )


def test_staged_job_subscriber_and_domain_audit_roll_back_together(requester_id):
    parent, created = service.stage_job_execution(_spec(requester_id))
    assert created
    db.session.commit()
    parent_id = parent.id
    child_spec = _spec(
        requester_id, operation='fixture_child', parent_job_id=parent_id, parameters={'fixture': 'child'}
    )
    child, created = service.stage_job_execution(child_spec)
    assert created
    child_id = child.id
    assert child.parent_job_id == parent_id
    assert child.max_attempts == 1
    assert child.parameter_fingerprint == service.payload_fingerprint(child_spec.parameters)
    assert JobExecutionSubscriber.query.filter_by(job_execution_id=child_id, user_id=requester_id).count() == 1
    db.session.add(AuditEvent(
        actor_user_id=requester_id,
        target_type='job_execution',
        target_id=child.public_id,
        action='fixture.admission',
        summary='Synthetic admission evidence',
    ))
    db.session.flush()
    db.session.rollback()

    assert db.session.get(JobExecution, child_id) is None
    assert JobExecutionSubscriber.query.filter_by(job_execution_id=child_id).count() == 0
    assert AuditEvent.query.filter_by(action='fixture.admission').count() == 0
    assert db.session.get(JobExecution, parent_id) is not None


def test_staging_duplicate_does_not_attach_or_commit(requester_id):
    spec = _spec(requester_id)
    first, created = service.stage_job_execution(spec)
    assert created
    first_id = first.id
    duplicate, created = service.stage_job_execution(replace(spec, requested_by_user_id=8))
    assert not created
    assert duplicate.id == first_id
    assert JobExecutionSubscriber.query.filter_by(job_execution_id=first_id).count() == 1
    db.session.rollback()
    assert db.session.get(JobExecution, first_id) is None


def test_normal_create_or_attach_persists_initial_subscriber(requester_id):
    spec = _spec(requester_id)
    job, created = service.create_or_attach_job(
        job_type=spec.job_type,
        operation=spec.operation,
        queue_name=spec.queue_name,
        workload_class=spec.workload_class,
        requested_by_user_id=requester_id,
        parameters=spec.parameters,
    )
    assert created
    job_id = job.id
    db.session.rollback()
    assert db.session.get(JobExecution, job_id) is not None
    assert JobExecutionSubscriber.query.filter_by(job_execution_id=job_id, user_id=requester_id).count() == 1

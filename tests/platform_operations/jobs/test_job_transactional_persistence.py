"""Canonical job staging shares one transaction with domain admission evidence."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from flask import Flask
from sqlalchemy import Column, Integer, MetaData, Table, insert

from app.extensions.db import db
from app.infrastructure_automation.kubernetes import run_reservation
from app.models.audit import AuditEvent
from app.models.automation import AutomationRunReservationAdoption
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
    integrations = Table('integration_instances', metadata, Column('id', Integer, primary_key=True))
    for model in (JobExecution, JobExecutionSubscriber, AuditEvent, AutomationRunReservationAdoption):
        model.__table__.to_metadata(metadata)
    with app.app_context():
        try:
            with db.engine.begin() as connection:
                connection.exec_driver_sql('PRAGMA foreign_keys=ON')
                metadata.create_all(connection)
                connection.execute(insert(users), [{'id': 7}, {'id': 8}])
                connection.execute(insert(integrations), {'id': 31})
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


@pytest.mark.parametrize('commit', [False, True])
def test_domain_stages_new_child_subscriber_adoption_and_audit_together(requester_id, monkeypatch, commit):
    parent, created = service.stage_job_execution(_spec(requester_id, integration_instance_id=31))
    assert created
    db.session.commit()
    parent_id = parent.id
    reservation_id = str(uuid4())
    fingerprint = 'a' * 64
    spec = _spec(
        requester_id,
        job_type='infrastructure_automation',
        operation=run_reservation.RUN_OPERATION,
        integration_type='configuration_automation',
        integration_instance_id=31,
        scope_type='ansible_source_connection',
        scope_key='31',
        parent_job_id=parent_id,
        parameters={
            'reservation_id': reservation_id,
            'plan_job_public_id': parent.public_id,
            'plan_fingerprint': fingerprint,
        },
    )
    # Isolate persistence, not actual approval or PostgreSQL lock behavior.
    monkeypatch.setattr(run_reservation, 'lock_reserved_plan', lambda **kwargs: parent)
    child = run_reservation.stage_run_reservation_adoption(
        reservation_id=reservation_id,
        connection_id=31,
        plan_fingerprint=fingerprint,
        actor_id=requester_id,
        run_spec=spec,
    )
    child_id = child.id
    assert JobExecutionSubscriber.query.filter_by(job_execution_id=child_id).count() == 1
    assert AutomationRunReservationAdoption.query.filter_by(run_job_id=child_id).count() == 1
    assert AuditEvent.query.filter_by(target_id=reservation_id).count() == 1
    if commit:
        db.session.commit()
    db.session.rollback()
    assert (db.session.get(JobExecution, child_id) is not None) is commit
    assert JobExecutionSubscriber.query.filter_by(job_execution_id=child_id).count() == int(commit)
    assert AutomationRunReservationAdoption.query.filter_by(run_job_id=child_id).count() == int(commit)
    assert AuditEvent.query.filter_by(target_id=reservation_id).count() == int(commit)
    assert db.session.get(JobExecution, parent_id) is not None

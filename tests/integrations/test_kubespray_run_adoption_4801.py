"""Durable reservation adoption correlation, never execution authorization."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, select
from sqlalchemy.exc import IntegrityError

from app.infrastructure_automation.kubernetes import run_reservation as service
from app.models.audit import AuditEvent
from app.models.automation import AutomationRunReservationAdoption


@pytest.fixture
def adoption_table():
    metadata = MetaData()
    Table('job_executions', metadata, Column('id', Integer, primary_key=True))
    Table('users', metadata, Column('id', Integer, primary_key=True))
    table = AutomationRunReservationAdoption.__table__.to_metadata(metadata)
    engine = create_engine('sqlite://')
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
            metadata.create_all(conn)
            conn.execute(insert(metadata.tables['users']), {'id': 7})
            conn.execute(insert(metadata.tables['job_executions']), [{'id': i} for i in range(1, 5)])
        yield engine, table
    finally:
        engine.dispose()


def _record():
    return {
        'reservation_id': str(uuid4()),
        'plan_job_id': 1,
        'run_job_id': 2,
        'adopted_by_user_id': 7,
        'adopted_at': datetime.now(UTC),
    }


@pytest.mark.parametrize('conflict', ['reservation', 'plan', 'run', 'same_job', 'missing_job'])
def test_adoption_database_exclusion(adoption_table, conflict):
    engine, table = adoption_table
    first = _record()
    with engine.begin() as conn:
        conn.execute(insert(table), first)
    second = _record() | {'plan_job_id': 3, 'run_job_id': 4}
    if conflict == 'reservation':
        second['reservation_id'] = first['reservation_id']
    elif conflict == 'plan':
        second['plan_job_id'] = first['plan_job_id']
    elif conflict == 'run':
        second['run_job_id'] = first['run_job_id']
    elif conflict == 'same_job':
        second['run_job_id'] = 3
    else:
        second['run_job_id'] = 99
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert(table), second)
    with engine.begin() as conn:
        assert len(conn.execute(select(table)).all()) == 1


def _child(reservation_id, plan):
    payload = {
        'reservation_id': reservation_id,
        'plan_job_public_id': plan.public_id,
        'plan_fingerprint': 'a' * 64,
    }
    return SimpleNamespace(
        id=2, public_id='child', parent_job_id=plan.id,
        operation=service.RUN_OPERATION, job_type='infrastructure_automation', queue_name='automation',
        integration_type='configuration_automation', integration_instance_id=31,
        scope_type='ansible_source_connection', scope_key='31', requested_by_user_id=7,
        status='queued', max_attempts=1, attempt_count=0, started_at=None, completed_at=None,
        cancel_requested_at=None, celery_task_id='fixture-task', active_deduplication_key='fixture',
        payload_json=payload, parameter_fingerprint=service.payload_fingerprint(payload),
    )


@pytest.mark.parametrize('failure', [None, 'other_child', 'parent_job_id', 'attempt_count', 'operation', 'payload_json'])
def test_stage_adoption_requires_exact_child_and_flushes_audit_without_commit(monkeypatch, failure):
    reservation_id = str(uuid4())
    plan = SimpleNamespace(id=1, public_id='plan', integration_instance_id=31)
    child = _child(reservation_id, plan)
    if failure not in (None, 'other_child'):
        setattr(child, failure, None)
    monkeypatch.setattr(service, 'lock_reserved_plan', lambda **kwargs: plan)
    staged = []
    events = []
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=SimpleNamespace(
        get=lambda *args, **kwargs: child,
        execute=lambda statement: SimpleNamespace(
            scalar_one_or_none=lambda: 9 if failure == 'other_child' else None
        ),
        add=staged.append,
        flush=lambda: events.append('flush'),
    )))
    kwargs = dict(reservation_id=reservation_id, connection_id=31, plan_fingerprint='a' * 64,
                  actor_id=7, run_job_id=2)
    if failure is not None:
        with pytest.raises(service.TargetReservationDenied):
            service.stage_run_reservation_adoption(**kwargs)
        assert staged == []
        return
    service.stage_run_reservation_adoption(**kwargs)
    assert len(staged) == 2
    assert isinstance(staged[0], AutomationRunReservationAdoption)
    assert staged[0].run_job_id == 2
    assert isinstance(staged[1], AuditEvent)
    assert staged[1].metadata_json['execution_authorized'] is False
    assert events == ['flush']

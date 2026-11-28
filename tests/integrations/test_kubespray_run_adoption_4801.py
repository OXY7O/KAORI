"""Durable reservation adoption correlation, never execution authorization."""

from dataclasses import replace
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


def _spec(reservation_id, plan):
    return service.JobCreationSpec(
        job_type='infrastructure_automation',
        operation=service.RUN_OPERATION,
        queue_name='automation',
        workload_class='validation',
        requested_by_user_id=7,
        integration_type='configuration_automation',
        integration_instance_id=31,
        scope_type='ansible_source_connection',
        scope_key='31',
        parent_job_id=plan.id,
        parameters=_child(reservation_id, plan).payload_json,
        max_attempts=1,
    )


@pytest.mark.parametrize('failure', [
    None, 'other_child', 'duplicate', 'parent_job_id', 'attempt_count', 'operation', 'payload_json',
    'spec_parent', 'spec_operation', 'spec_task', 'spec_payload',
])
def test_stage_adoption_requires_new_exact_child_and_flushes_audit_without_commit(monkeypatch, failure):
    reservation_id = str(uuid4())
    plan = SimpleNamespace(id=1, public_id='plan', integration_instance_id=31)
    child = _child(reservation_id, plan)
    spec = _spec(reservation_id, plan)
    if failure in ('parent_job_id', 'attempt_count', 'operation', 'payload_json'):
        setattr(child, failure, None)
    if failure == 'spec_parent':
        spec = replace(spec, parent_job_id=99)
    elif failure == 'spec_operation':
        spec = replace(spec, operation='fixture')
    elif failure == 'spec_task':
        spec = replace(spec, celery_task_id='previous-dispatch')
    elif failure == 'spec_payload':
        spec = replace(spec, payload={'fixture': 'different'})

    staged = []
    events = []

    def lock(**kwargs):
        events.append('lock')
        return plan

    def stage(actual):
        assert actual is spec
        events.append('stage')
        return child, failure != 'duplicate'

    monkeypatch.setattr(service, 'lock_reserved_plan', lock)
    monkeypatch.setattr(service, 'stage_job_execution', stage)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=SimpleNamespace(
        execute=lambda statement: SimpleNamespace(
            scalar_one_or_none=lambda: 9 if failure == 'other_child' else None
        ),
        add=staged.append,
        flush=lambda: events.append('flush'),
    )))
    kwargs = dict(reservation_id=reservation_id, connection_id=31, plan_fingerprint='a' * 64,
                  actor_id=7, run_spec=spec)
    if failure is not None:
        with pytest.raises(service.TargetReservationDenied):
            service.stage_run_reservation_adoption(**kwargs)
        assert staged == []
        if failure == 'other_child' or failure.startswith('spec_'):
            assert events == ['lock']
        return
    assert service.stage_run_reservation_adoption(**kwargs) is child
    assert len(staged) == 2
    assert isinstance(staged[0], AutomationRunReservationAdoption)
    assert staged[0].run_job_id == 2
    assert isinstance(staged[1], AuditEvent)
    assert staged[1].metadata_json['execution_authorized'] is False
    assert events == ['lock', 'stage', 'flush']


@pytest.mark.parametrize('failure', [None, 'missing_claim', 'released', 'wrong_plan', 'wrong_actor', 'adopted', 'stale'])
def test_lock_reserved_plan_requalifies_exact_seven_active_claims(monkeypatch, failure):
    reservation_id = str(uuid4())
    plan = SimpleNamespace(id=1)
    keys = tuple(f'fixture:{i}' for i in range(7))
    rows = [
        SimpleNamespace(
            plan_job_id=1, resource_key=key, active_resource_key=key,
            plan_fingerprint='a' * 64, reserved_by_user_id=7, released_at=None,
        )
        for key in keys
    ]
    if failure == 'missing_claim':
        rows.pop()
    elif failure == 'released':
        rows[0].released_at = datetime.now(UTC)
    elif failure == 'wrong_plan':
        rows[0].plan_job_id = 99
    elif failure == 'wrong_actor':
        rows[0].reserved_by_user_id = 99
    acknowledgements = iter([{'requested_by': 7}, None if failure == 'stale' else {'requested_by': 7}])
    monkeypatch.setattr(service, 'review_current_plan_acknowledgement', lambda **kwargs: next(acknowledgements))
    monkeypatch.setattr(service, '_plan_targets', lambda *args: (plan, keys))
    monkeypatch.setattr(service, '_reservation_rows', lambda identity: rows)
    monkeypatch.setattr(service, '_existing_adoption', lambda *args: failure == 'adopted')
    kwargs = dict(reservation_id=reservation_id, connection_id=31, plan_fingerprint='a' * 64, actor_id=7)
    if failure is None:
        assert service.lock_reserved_plan(**kwargs) is plan
    else:
        with pytest.raises(service.TargetReservationDenied):
            service.lock_reserved_plan(**kwargs)


def test_review_release_refuses_adoption_without_consulting_child_status(monkeypatch):
    reservation_id = str(uuid4())
    plan = SimpleNamespace(id=1, operation=service.PLAN_OPERATION, requested_by_user_id=7)
    rows = [
        SimpleNamespace(
            plan_job_id=1, plan_fingerprint='a' * 64, reserved_by_user_id=7,
            released_at=None, active_resource_key=f'fixture:{i}', resource_key=f'fixture:{i}',
        )
        for i in range(7)
    ]
    events = []
    monkeypatch.setattr(service, 'begin_security_review_transaction', lambda: None)
    monkeypatch.setattr(service, 'lock_explicit_permissions', lambda *args: True)
    monkeypatch.setattr(service, '_reservation_rows', lambda identity: rows)
    monkeypatch.setattr(service, '_existing_adoption', lambda *args: True)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=SimpleNamespace(
        execute=lambda statement: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [1])),
        get=lambda *args, **kwargs: plan,
        rollback=lambda: events.append('rollback'),
    )))
    with pytest.raises(service.TargetReservationDenied):
        service.release_review_targets(reservation_id=reservation_id, actor_id=7)
    assert all(row.released_at is None and row.active_resource_key == row.resource_key for row in rows)
    assert events == ['rollback']

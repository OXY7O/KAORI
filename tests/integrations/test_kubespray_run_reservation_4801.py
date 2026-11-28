"""Persistent exclusion schema and exact target correlation; no host access."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.infrastructure_automation.kubernetes import run_reservation as service
from app.models.automation import AutomationRunTargetClaim


def _members(connection_id=31):
    return [
        SimpleNamespace(
            host_id=f'00000000-0000-4000-8000-{index:012d}',
            integration_instance_id=connection_id,
            enabled=True,
            host=SimpleNamespace(address=f'10.0.0.{index}'),
        )
        for index in range(1, 4)
    ]


def test_resource_keys_are_order_independent_and_exclude_cross_connection_aliases():
    members = _members()
    first = service._resource_keys(31, members)
    assert len(first) == 7
    assert first == service._resource_keys(31, list(reversed(members)))
    second = service._resource_keys(32, _members(32))
    assert len(set(first) & set(second)) == 6
    assert not any('10.0.0.' in key for key in first)


@pytest.mark.parametrize('failure', ['missing', 'duplicate_host', 'duplicate_endpoint', 'foreign', 'disabled'])
def test_unqualified_membership_denied(failure):
    members = _members()
    if failure == 'missing':
        members.pop()
    elif failure == 'duplicate_host':
        members[1].host_id = members[0].host_id
    elif failure == 'duplicate_endpoint':
        members[1].host.address = members[0].host.address
    elif failure == 'foreign':
        members[0].integration_instance_id = 32
    else:
        members[0].enabled = False
    with pytest.raises(service.TargetReservationDenied):
        service._resource_keys(31, members)


@pytest.fixture
def claims():
    metadata = MetaData()
    Table('job_executions', metadata, Column('id', Integer, primary_key=True))
    Table('users', metadata, Column('id', Integer, primary_key=True))
    table = AutomationRunTargetClaim.__table__.to_metadata(metadata)
    engine = create_engine('sqlite://')
    metadata.create_all(engine)
    try:
        yield engine, table
    finally:
        engine.dispose()


def _claim(plan, key, reservation=None):
    return {
        'reservation_id': reservation or str(uuid4()),
        'plan_job_id': plan,
        'resource_key': key,
        'active_resource_key': key,
        'plan_fingerprint': 'a' * 64,
        'reserved_by_user_id': 7,
        'reserved_at': datetime.now(UTC),
    }


def test_active_claim_conflict_survives_commit_and_explicit_release_retains_history(claims):
    engine, table = claims
    key = 'kubespray:host:fixture'
    with engine.begin() as conn:
        conn.execute(insert(table), _claim(1, key))
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert(table), _claim(2, key))
    with engine.begin() as conn:
        conn.execute(update(table).where(table.c.plan_job_id == 1).values(
            active_resource_key=None, released_at=datetime.now(UTC)
        ))
    with engine.begin() as conn:
        conn.execute(insert(table), _claim(2, key))
        assert len(conn.execute(select(table)).all()) == 2
    # A released immutable Plan cannot be recycled.
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert(table), _claim(1, 'kubespray:host:fixture') | {
            'active_resource_key': None, 'released_at': datetime.now(UTC),
        })


def test_conflicting_multi_resource_insert_rolls_back_all_claims(claims):
    engine, table = claims
    with engine.begin() as conn:
        conn.execute(insert(table), _claim(1, 'kubespray:host:fixture'))
    reservation = str(uuid4())
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert(table), [
            _claim(2, 'kubespray:connection:32', reservation),
            _claim(2, 'kubespray:host:fixture', reservation),
        ])
    with engine.begin() as conn:
        assert len(conn.execute(select(table)).all()) == 1


def test_release_shape_cannot_clear_claim_without_timestamp(claims):
    engine, table = claims
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert(table), _claim(1, 'kubespray:host:fixture') | {'active_resource_key': None})

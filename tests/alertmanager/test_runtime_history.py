from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')
from app import create_app
from app.extensions import db
from app.integrations.runtime.contracts import CapabilitySnapshot, HealthState, RuntimeState
from app.integrations.runtime.repository import persist_runtime_state
from app.models.runtime import IntegrationRuntimeObservation


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()

def test_runtime_state_is_persisted(app):
    state = RuntimeState(provider='alertmanager', instance_id='1', instance_name='AM', observed_at=datetime.now(UTC), readiness='ready', health=HealthState('healthy', 96), diagnostics=(), snapshot=CapabilitySnapshot('v033','current',('alerts_v2',),datetime.now(UTC)))
    persist_runtime_state(state, trigger_type='manual')
    row = IntegrationRuntimeObservation.query.one()
    assert row.health_score == 96
    assert row.capability_snapshot['capabilities'] == ['alerts_v2']


def test_runtime_history_view_marks_recovery_and_capability_change(app):
    from app.integrations.runtime.presentation import runtime_history_view

    observed_at = datetime.now(UTC)
    unhealthy = IntegrationRuntimeObservation(
        provider='alertmanager',
        instance_id='1',
        instance_name='AM',
        trigger_type='scheduled',
        readiness='ready',
        health_status='unhealthy',
        health_score=20,
        capability_snapshot={'capabilities': ['alerts_v2']},
        diagnostics=[],
        observed_at=observed_at,
    )
    healthy = IntegrationRuntimeObservation(
        provider='alertmanager',
        instance_id='1',
        instance_name='AM',
        trigger_type='manual',
        readiness='ready',
        health_status='healthy',
        health_score=95,
        capability_snapshot={'capabilities': ['alerts_v2', 'silences_v2']},
        diagnostics=[],
        observed_at=observed_at,
    )
    db.session.add_all([unhealthy, healthy])
    db.session.flush()

    view = runtime_history_view(
        [healthy, unhealthy],
        pagination={
            'page': 1,
            'per_page': 5,
            'total_items': 2,
            'total_pages': 1,
        },
    )

    assert view['rows'][0]['transition']['kind'] == 'recovered'
    assert view['rows'][0]['added_capabilities'] == ['silences_v2']
    assert view['rows'][0]['capability_changed'] is True


def test_runtime_history_view_uses_oldest_row_as_baseline(app):
    from app.integrations.runtime.presentation import runtime_history_view

    observed_at = datetime.now(UTC)
    baseline = IntegrationRuntimeObservation(
        provider='alertmanager', instance_id='1', instance_name='AM',
        trigger_type='scheduled', readiness='ready', health_status='healthy',
        health_score=90, capability_snapshot={'capabilities': ['alerts_v2']},
        diagnostics=[], observed_at=observed_at,
    )
    current = IntegrationRuntimeObservation(
        provider='alertmanager', instance_id='1', instance_name='AM',
        trigger_type='scheduled', readiness='ready', health_status='healthy',
        health_score=92, capability_snapshot={'capabilities': ['alerts_v2']},
        diagnostics=[], observed_at=observed_at,
    )
    db.session.add_all([baseline, current])
    db.session.flush()

    view = runtime_history_view(
        [current, baseline],
        pagination={'page': 1, 'per_page': 1, 'total_items': 2, 'total_pages': 2},
    )

    assert len(view['rows']) == 1
    assert view['rows'][0]['capability_changed'] is False
    assert view['rows'][0]['transition'] is None


def test_runtime_history_is_append_only_until_data_lifecycle_cleanup(app):
    base = datetime.now(UTC) - timedelta(hours=2)
    rows = [
        IntegrationRuntimeObservation(
            provider='alertmanager',
            instance_id='retained-instance',
            instance_name='Retained AM',
            trigger_type='scheduled',
            readiness='ready',
            health_status='healthy',
            health_score=90,
            capability_snapshot={'capabilities': ['alerts_v2']},
            diagnostics=[],
            observed_at=base + timedelta(minutes=index),
        )
        for index in range(100)
    ]
    unrelated = IntegrationRuntimeObservation(
        provider='alertmanager',
        instance_id='other-instance',
        instance_name='Other AM',
        trigger_type='scheduled',
        readiness='ready',
        health_status='healthy',
        health_score=90,
        capability_snapshot={'capabilities': ['alerts_v2']},
        diagnostics=[],
        observed_at=base,
    )
    db.session.add_all([*rows, unrelated])
    db.session.commit()
    oldest_id = rows[0].id

    newest_state = RuntimeState(
        provider='alertmanager',
        instance_id='retained-instance',
        instance_name='Retained AM',
        observed_at=base + timedelta(minutes=101),
        readiness='ready',
        health=HealthState('healthy', 97),
        diagnostics=(),
        snapshot=CapabilitySnapshot(
            'v033',
            'current',
            ('alerts_v2', 'silences_v2'),
            base + timedelta(minutes=101),
        ),
    )
    newest = persist_runtime_state(newest_state, trigger_type='manual')

    retained_query = IntegrationRuntimeObservation.query.filter_by(
        provider='alertmanager',
        instance_id='retained-instance',
    )
    assert retained_query.count() == 101
    assert db.session.get(IntegrationRuntimeObservation, oldest_id) is not None
    assert db.session.get(IntegrationRuntimeObservation, newest.id) is not None
    assert IntegrationRuntimeObservation.query.filter_by(
        provider='alertmanager',
        instance_id='other-instance',
    ).count() == 1

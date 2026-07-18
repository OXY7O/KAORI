from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')
from app import create_app
from app.extensions import db
from app.integrations.runtime.contracts import CapabilitySnapshot, HealthState, RuntimeState
from app.integrations.runtime.repository import persist_runtime_state
from app.models.integration_runtime import IntegrationRuntimeObservation


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

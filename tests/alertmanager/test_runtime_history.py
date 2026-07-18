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
        db.create_all(); yield application; db.session.remove(); db.drop_all()

def test_runtime_state_is_persisted(app):
    state = RuntimeState(provider='alertmanager', instance_id='1', instance_name='AM', observed_at=datetime.now(UTC), readiness='ready', health=HealthState('healthy', 96), diagnostics=(), snapshot=CapabilitySnapshot('v033','current',('alerts_v2',),datetime.now(UTC)))
    persist_runtime_state(state, trigger_type='manual')
    row = IntegrationRuntimeObservation.query.one()
    assert row.health_score == 96
    assert row.capability_snapshot['capabilities'] == ['alerts_v2']

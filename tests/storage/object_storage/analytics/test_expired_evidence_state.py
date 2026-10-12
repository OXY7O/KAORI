from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.storage.object_storage.analytics.materialization import (
    analytics_snapshot_state,
    forecast_snapshot_state,
)


@pytest.mark.parametrize('reader', [analytics_snapshot_state, forecast_snapshot_state])
@pytest.mark.parametrize('status', ['ready', 'pending', 'failed'])
def test_expired_payload_is_never_misrepresented_as_usable_stale_worker_evidence(reader, status) -> None:
    now = datetime.now(UTC)
    snapshot = SimpleNamespace(
        status=status,
        payload_json={'schema': 'object-storage-analytics.v1'},
        generated_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        stale_grace_minutes=15,
        last_attempt_at=now - timedelta(minutes=3),
        last_error='last refresh failed' if status == 'failed' else None,
    )
    state = reader(snapshot)
    assert not state['usable']
    assert state['label'].startswith('Expired')
    assert state['tone'] == 'critical'
    assert state['last_attempt_at'] == snapshot.last_attempt_at


@pytest.mark.parametrize('reader', [analytics_snapshot_state, forecast_snapshot_state])
def test_failed_snapshot_preserves_last_good_within_grace(reader) -> None:
    now = datetime.now(UTC)
    snapshot = SimpleNamespace(
        status='failed',
        payload_json={'old': 'committed'},
        generated_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=5),
        stale_grace_minutes=60,
        last_attempt_at=now,
        last_error='timeout',
    )
    state = reader(snapshot)
    assert state['usable']
    assert state['label'] == 'Stale · Failed'
    assert state['last_error'] == 'timeout'

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.storage.object_storage.analytics import materialization


@pytest.mark.parametrize('status', ['ready', 'pending', 'failed'])
@pytest.mark.parametrize('kind', ['analytics', 'forecast'])
def test_scheduled_due_checks_retry_failure_without_discarding_last_good(
    monkeypatch: pytest.MonkeyPatch, status: str, kind: str
) -> None:
    now = datetime.now(UTC)
    snapshot = SimpleNamespace(
        status=status,
        payload_json={'schema': 'committed'},
        generated_at=now - timedelta(minutes=2),
        expires_at=now + timedelta(minutes=13),
    )
    if kind == 'analytics':
        monkeypatch.setattr(materialization, 'get_analytics_snapshot', lambda **_kw: snapshot)
        due = materialization.analytics_snapshot_due(system_id='one', time_range='24h')
    else:
        monkeypatch.setattr(materialization, 'get_forecast_snapshot', lambda **_kw: snapshot)
        due = materialization.forecast_snapshot_due(system_id='one', history_window='30d')

    assert due is (status == 'failed')
    # The failed row still retains last-good evidence for separately labeled continuity.
    assert snapshot.payload_json is not None


@pytest.mark.parametrize('kind', ['analytics', 'forecast'])
def test_scheduled_due_checks_distinguish_expired_and_missing_evidence(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    snapshot = SimpleNamespace(
        status='ready',
        payload_json={'schema': 'committed'},
        generated_at=datetime.now(UTC) - timedelta(hours=1),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    if kind == 'analytics':
        monkeypatch.setattr(materialization, 'get_analytics_snapshot', lambda **_kw: snapshot)
        due = lambda: materialization.analytics_snapshot_due(system_id='one', time_range='24h')
    else:
        monkeypatch.setattr(materialization, 'get_forecast_snapshot', lambda **_kw: snapshot)
        due = lambda: materialization.forecast_snapshot_due(system_id='one', history_window='30d')
    assert due() is True
    snapshot.expires_at = datetime.now(UTC) + timedelta(minutes=15)
    snapshot.payload_json = None
    assert due() is True

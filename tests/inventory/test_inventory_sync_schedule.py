from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.inventory import schedule


def test_update_policy_resets_next_run(monkeypatch) -> None:
    now = datetime(2026, 7, 24, 5, 0, tzinfo=UTC)
    policy = SimpleNamespace(
        enabled=False,
        interval_minutes=60,
        updated_by_user_id=None,
        next_run_at=None,
    )
    committed: list[bool] = []

    monkeypatch.setattr(schedule, '_utcnow', lambda: now)
    monkeypatch.setattr(schedule, 'get_inventory_sync_policy', lambda: policy)
    monkeypatch.setattr(schedule.db, 'session', SimpleNamespace(commit=lambda: committed.append(True)))

    result = schedule.update_inventory_sync_policy(enabled=True, interval_minutes=30, user_id=7)

    assert result is policy
    assert policy.enabled is True
    assert policy.interval_minutes == 30
    assert policy.updated_by_user_id == 7
    assert policy.next_run_at == now + timedelta(minutes=30)
    assert committed == [True]


def test_update_policy_rejects_unsafe_interval() -> None:
    for interval in (0, 4, 1441):
        try:
            schedule.update_inventory_sync_policy(enabled=True, interval_minutes=interval, user_id=7)
        except ValueError:
            continue
        raise AssertionError(f'Expected interval {interval} to be rejected.')

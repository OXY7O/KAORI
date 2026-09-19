from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.kubernetes.cluster.quick_sync import sync_snapshot_visible_to_user
from app.platform_operations.jobs.policies import service


def _definition() -> SimpleNamespace:
    return SimpleNamespace(
        key='kubernetes.inventory.sync',
        name='Inventory Sync',
        schedule_supported=True,
        minimum_interval_minutes=5,
        maximum_interval_minutes=1440,
        default_interval_minutes=60,
    )


def test_update_policy_resets_next_run(monkeypatch) -> None:
    now = datetime(2026, 7, 24, 5, 0, tzinfo=UTC)
    policy = SimpleNamespace(
        enabled=False,
        trigger_type='interval',
        interval_minutes=60,
        updated_by_user_id=None,
        next_run_at=None,
        last_dispatch_status=None,
        last_dispatch_message=None,
    )
    committed: list[bool] = []

    monkeypatch.setattr(service, 'utcnow', lambda: now)
    monkeypatch.setattr(service, 'get_job_definition', lambda _key: _definition())
    monkeypatch.setattr(service, 'get_or_create_job_policy', lambda _key: policy)
    monkeypatch.setattr(service.db, 'session', SimpleNamespace(commit=lambda: committed.append(True)))

    result = service.update_job_policy(
        job_key='kubernetes.inventory.sync',
        enabled=True,
        interval_minutes=30,
        user_id=7,
    )

    assert result is policy
    assert policy.enabled is True
    assert policy.trigger_type == 'interval'
    assert policy.interval_minutes == 30
    assert policy.updated_by_user_id == 7
    assert policy.next_run_at == now + timedelta(minutes=30)
    assert policy.last_dispatch_status is None
    assert committed == [True]


def test_update_policy_rejects_unsafe_interval(monkeypatch) -> None:
    monkeypatch.setattr(service, 'get_job_definition', lambda _key: _definition())

    for interval in (0, 4, 1441):
        try:
            service.update_job_policy(
                job_key='kubernetes.inventory.sync',
                enabled=True,
                interval_minutes=interval,
                user_id=7,
            )
        except ValueError:
            continue
        raise AssertionError(f'Expected interval {interval} to be rejected.')


def test_scheduled_inventory_sync_is_not_visible_as_user_toast() -> None:
    assert (
        sync_snapshot_visible_to_user(
            {'requested_by_user_id': None},
            user_id=7,
        )
        is False
    )


def test_manual_inventory_sync_toast_is_scoped_to_requester() -> None:
    snapshot = {'requested_by_user_id': 7}

    assert sync_snapshot_visible_to_user(snapshot, user_id=7) is True
    assert sync_snapshot_visible_to_user(snapshot, user_id=8) is False

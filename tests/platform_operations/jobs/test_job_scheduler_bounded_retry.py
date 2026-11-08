from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.platform_operations.jobs.scheduler import FAILED_DISPATCH_RETRY_MINUTES, _record_failed_dispatch


def test_failed_dispatch_retries_in_bounded_window() -> None:
    now = datetime(2026, 10, 12, tzinfo=UTC)
    claimed = now + timedelta(minutes=60)
    policy = SimpleNamespace(
        enabled=True, next_run_at=claimed, last_dispatch_status='dispatching', last_dispatch_message=''
    )

    assert _record_failed_dispatch(policy, claim_next_run_at=claimed, now=now, message='broker unavailable')
    assert policy.next_run_at == now + timedelta(minutes=FAILED_DISPATCH_RETRY_MINUTES)
    assert policy.last_dispatch_status == 'failed'
    assert policy.last_dispatch_message == 'broker unavailable'


def test_failure_does_not_override_concurrent_policy_edit() -> None:
    now = datetime(2026, 10, 12, tzinfo=UTC)
    claimed = now + timedelta(minutes=60)
    changed = now + timedelta(minutes=120)
    policy = SimpleNamespace(
        enabled=True, next_run_at=changed, last_dispatch_status='dispatching', last_dispatch_message='changed'
    )

    assert not _record_failed_dispatch(policy, claim_next_run_at=claimed, now=now, message='broker unavailable')
    assert policy.next_run_at == changed
    assert policy.last_dispatch_message == 'changed'


def test_failed_dispatch_never_reenables_disabled_policy() -> None:
    now = datetime(2026, 10, 12, tzinfo=UTC)
    claimed = now + timedelta(minutes=60)
    policy = SimpleNamespace(
        enabled=False, next_run_at=claimed, last_dispatch_status='dispatching', last_dispatch_message=''
    )

    assert _record_failed_dispatch(policy, claim_next_run_at=claimed, now=now, message='worker unavailable')
    assert not policy.enabled
    assert policy.next_run_at == claimed

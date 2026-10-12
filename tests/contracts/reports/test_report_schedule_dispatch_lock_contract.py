from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.reports.schedules.service import (
    FAILED_REPORT_SCHEDULE_RETRY_MINUTES,
    _retry_unadmitted_schedule,
)

ROOT = Path(__file__).resolve().parents[3]


def test_unadmitted_due_failure_is_eligible_for_bounded_retry() -> None:
    now = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
    schedule = SimpleNamespace(
        is_enabled=True,
        next_run_at=now + timedelta(days=1),
    )
    _retry_unadmitted_schedule(schedule, failed_at=now, trigger_source='scheduler')
    assert schedule.next_run_at == now + timedelta(minutes=FAILED_REPORT_SCHEDULE_RETRY_MINUTES)


def test_manual_and_paused_failures_do_not_change_due_time() -> None:
    now = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
    for enabled, trigger in [(True, 'manual'), (False, 'scheduler')]:
        original = now + timedelta(days=1)
        schedule = SimpleNamespace(is_enabled=enabled, next_run_at=original)
        _retry_unadmitted_schedule(schedule, failed_at=now, trigger_source=trigger)
        assert schedule.next_run_at == original


def test_due_schedule_rereads_locked_row_and_checks_active_run() -> None:
    source = (ROOT / 'app/reports/schedules/service.py').read_text(encoding='utf-8')
    failures = (ROOT / 'app/reports/schedules/failures.py').read_text(encoding='utf-8')
    assert '.with_for_update()' in source
    assert '.execution_options(populate_existing=True)' in source
    assert "ReportScheduleRun.status.in_(('started', 'queued'))" in source
    assert "if trigger_source == 'scheduler':" in source
    assert "skipped = success and report_id is None" in source
    assert "run.status == 'started'" in source
    assert "run.trigger_source == 'scheduler'" in failures
    assert 'timedelta(minutes=5)' in failures

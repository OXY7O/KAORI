from __future__ import annotations

from types import SimpleNamespace

from app.reports.schedules.support import get_run_delivery_channel_ids


def test_committed_delivery_intent_survives_definition_edit_and_deletion() -> None:
    run = SimpleNamespace(schedule_snapshot={'notification_channel_ids': [23, 24, 23]})
    changed_schedule = SimpleNamespace(notification_channel_ids_as_list=lambda: [91])
    assert get_run_delivery_channel_ids(run, changed_schedule) == [23, 24]
    assert get_run_delivery_channel_ids(run, None) == [23, 24]


def test_legacy_run_uses_existing_schedule_only_when_no_snapshot_intent() -> None:
    legacy = SimpleNamespace(schedule_snapshot={'name': 'Past report'})
    schedule = SimpleNamespace(notification_channel_ids_as_list=lambda: [5])
    assert get_run_delivery_channel_ids(legacy, schedule) == [5]
    assert get_run_delivery_channel_ids(legacy, None) == []


def test_explicit_empty_delivery_intent_does_not_adopt_new_recipients() -> None:
    run = SimpleNamespace(schedule_snapshot={'notification_channel_ids': []})
    schedule = SimpleNamespace(notification_channel_ids_as_list=lambda: [42])
    assert get_run_delivery_channel_ids(run, schedule) == []


def test_delivery_worker_rolls_back_failed_session_before_writing_delivery_attention() -> None:
    from pathlib import Path

    worker = (Path(__file__).resolve().parents[2] / 'app/reports/jobs/tasks.py').read_text(encoding='utf-8')
    delivery_failure = worker.split("current_app.logger.exception('Scheduled report", 1)[0]
    assert 'db.session.rollback()' in delivery_failure
    assert 'recovered_run = db.session.get(ReportScheduleRun, schedule_run_id)' in worker
    assert 'recovered_run.delivery_result = {' in worker

from __future__ import annotations

from pathlib import Path

from app.reports.schedules.presentation import present_delivery_result

ROOT = Path(__file__).resolve().parents[3]


def test_terminal_skipped_delivery_is_not_reported_as_pending() -> None:
    result = {'requested': 2, 'successful': 0, 'failed': 0, 'skipped': 2, 'duplicate': 0}
    assert present_delivery_result(result) == ('Delivery Skipped', 'warning')


def test_duplicate_dedup_delivery_preserves_prior_sent_status() -> None:
    result = {'requested': 1, 'successful': 0, 'failed': 0, 'skipped': 1, 'duplicate': 1}
    assert present_delivery_result(result) == ('Already Delivered', 'normal')


def test_mixed_and_no_delivery_states() -> None:
    assert present_delivery_result({'requested': 2, 'successful': 1, 'skipped': 1}) == (
        'Partial Delivery',
        'warning',
    )
    assert present_delivery_result({'requested': 1, 'failed': 1}) == ('Delivery Failed', 'critical')
    assert present_delivery_result({'requested': 0}) == ('No Delivery', 'unknown')


def test_schedule_posture_depends_on_persisted_dispatcher_policy_and_enabled_definitions() -> None:
    source = (ROOT / 'app/reports/schedules/service.py').read_text(encoding='utf-8')
    assert "JobPolicy.job_key == 'reports.schedule.dispatch'" in source
    assert 'Dispatcher Disabled' in source
    assert 'Waiting For Schedule' in source
    assert 'schedule.next_run_at = None' in source


def test_historical_run_uses_snapshot_identity() -> None:
    source = (ROOT / 'app/reports/schedules/presentation.py').read_text(encoding='utf-8')
    assert "str(snapshot.get('name') or schedule_context['name'])" in source

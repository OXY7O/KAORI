from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.storage.object_storage.analytics.materialization import (
    SnapshotSupersededError,
    _ensure_new_attempt_is_current,
    _verify_snapshot_claim,
)


@pytest.mark.parametrize('older,newer', [(5, 4), (5, None), (100, 99)])
def test_older_job_can_never_replace_newer_snapshot_claim(older, newer) -> None:
    with pytest.raises(SnapshotSupersededError, match='newer JobExecution'):
        _ensure_new_attempt_is_current(older, newer)


@pytest.mark.parametrize('previous,current', [(None, 5), (5, 5), (5, 6)])
def test_latest_or_restarted_job_may_claim(previous, current) -> None:
    _ensure_new_attempt_is_current(previous, current)


@pytest.mark.parametrize('mutation', ['new_job', 'new_attempt_same_job', 'already_ready', 'already_failed'])
def test_old_worker_cannot_overwrite_newer_ready_or_pending_evidence(mutation) -> None:
    stamp = datetime(2026, 10, 12, tzinfo=UTC)
    snapshot = SimpleNamespace(
        status='pending',
        last_job_execution_id=5,
        last_attempt_at=stamp,
    )
    if mutation == 'new_job':
        snapshot.last_job_execution_id = 6
    elif mutation == 'new_attempt_same_job':
        snapshot.last_attempt_at = stamp + timedelta(microseconds=10)
    elif mutation == 'already_ready':
        snapshot.status = 'ready'
    else:
        snapshot.status = 'failed'
    with pytest.raises(SnapshotSupersededError, match='superseded'):
        _verify_snapshot_claim(snapshot, job_execution_id=5, claimed_at=stamp)


def test_claim_matches_only_pending_owner_and_exact_attempt_token() -> None:
    stamp = datetime(2026, 10, 12, tzinfo=UTC)
    snapshot = SimpleNamespace(status='pending', last_job_execution_id=5, last_attempt_at=stamp)
    _verify_snapshot_claim(snapshot, job_execution_id=5, claimed_at=stamp)


def test_analytics_and_forecast_workers_recheck_claim_under_row_lock() -> None:
    root = Path(__file__).resolve().parents[4]
    materialization = (root / 'app/storage/object_storage/analytics/materialization.py').read_text(encoding='utf-8')
    tasks = (root / 'app/storage/object_storage/analytics/tasks.py').read_text(encoding='utf-8')
    assert materialization.count('.with_for_update().populate_existing()') >= 4
    assert 'def _locked_analytics_snapshot(' in materialization
    assert 'def _locked_forecast_snapshot(' in materialization
    assert materialization.count('_verify_snapshot_claim(') >= 4
    assert 'claimed_at = mark_analytics_pending(' in tasks
    assert 'claimed_at=claimed_at,' in tasks
    assert 'except SnapshotSupersededError:' in tasks

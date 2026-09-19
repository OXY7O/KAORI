from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from app.platform_operations.jobs import service
from app.platform_operations.jobs.serialization import to_json_compatible


class _Status(Enum):
    READY = 'ready'


@dataclass(frozen=True)
class _ResultRecord:
    observed_at: datetime
    count: int


def test_to_json_compatible_normalizes_nested_operational_values() -> None:
    observed_at = datetime(2026, 8, 6, 9, 10, 37, tzinfo=UTC)
    payload = {
        'observed_at': observed_at,
        'date': date(2026, 8, 6),
        'time': time(9, 10, 37),
        'ratio': Decimal('87.50'),
        'status': _Status.READY,
        'identifier': UUID('12345678-1234-5678-1234-567812345678'),
        'path': Path('/var/lib/kaori/report.pdf'),
        'record': _ResultRecord(observed_at=observed_at, count=2),
        'values': {3, 1, 2},
    }

    normalized = to_json_compatible(payload)

    assert normalized['observed_at'] == '2026-08-06T09:10:37+00:00'
    assert normalized['date'] == '2026-08-06'
    assert normalized['time'] == '09:10:37'
    assert normalized['ratio'] == '87.50'
    assert normalized['status'] == 'ready'
    assert normalized['identifier'] == '12345678-1234-5678-1234-567812345678'
    assert normalized['path'] == '/var/lib/kaori/report.pdf'
    assert normalized['record']['observed_at'] == '2026-08-06T09:10:37+00:00'
    assert normalized['values'] == [1, 2, 3]
    json.dumps(normalized)


def test_mark_job_succeeded_persists_json_safe_result_summary(monkeypatch) -> None:
    observed_at = datetime(2026, 8, 6, 9, 10, 37, tzinfo=UTC)
    job = SimpleNamespace(
        is_terminal=False,
        status='running',
        active_deduplication_key='job-key',
        completed_at=None,
        heartbeat_at=None,
        result_summary_json=None,
        result_type=None,
        result_reference=None,
        progress_total=1,
        progress_current=0,
        progress_message='Running',
    )
    commits: list[bool] = []

    monkeypatch.setattr(service, 'get_job_by_task_id', lambda _task_id: job)
    monkeypatch.setattr(service, '_append_automatic_terminal_audit', lambda _job: None)
    monkeypatch.setattr(service.db, 'session', SimpleNamespace(commit=lambda: commits.append(True)))

    result = service.mark_job_succeeded(
        'task-1',
        result_summary={'checked_at': observed_at},
        result_type='report_schedule_dispatch',
    )

    assert result is job
    assert job.status == 'succeeded'
    assert job.result_summary_json == {'checked_at': '2026-08-06T09:10:37+00:00'}
    assert job.progress_current == 1
    assert commits == [True]
    json.dumps(job.result_summary_json)

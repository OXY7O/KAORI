from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from app.reports.schedules import service


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def test_due_schedule_result_is_json_serializable(monkeypatch) -> None:
    due_at = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)
    checked_at = datetime(2026, 8, 6, 9, 10, 37, 328000, tzinfo=UTC)
    schedule = SimpleNamespace(id=17, name='Daily Capacity', next_run_at=due_at)
    fake_session = SimpleNamespace(scalars=lambda _statement: _ScalarResult([schedule]))
    monkeypatch.setattr(service.db, 'session', fake_session)

    result = service.run_due_schedules(limit=20, dry_run=True, now=checked_at)

    assert result == {
        'checked_at': '2026-08-06T09:10:37.328000+00:00',
        'dry_run': True,
        'due_count': 1,
        'results': [
            {
                'schedule_id': 17,
                'name': 'Daily Capacity',
                'status': 'due',
                'next_run_at': '2026-08-06T09:00:00+00:00',
            }
        ],
    }
    json.dumps(result)

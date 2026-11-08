from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.platform_operations.jobs import presentation


class _EmptyAggregateQuery:
    def group_by(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return []


def test_registered_queues_display_readiness_before_first_execution(monkeypatch):
    inspected = []
    monkeypatch.setattr(presentation.db, 'session', SimpleNamespace(query=lambda *_args: _EmptyAggregateQuery()))
    monkeypatch.setattr(
        presentation,
        'list_job_definitions',
        lambda: [
            SimpleNamespace(queue_name='maintenance'),
            SimpleNamespace(queue_name='inventory'),
        ],
    )
    monkeypatch.setattr(presentation, 'inspect_celery_topology', lambda: inspected.append(True) or {})
    monkeypatch.setattr(
        presentation,
        'get_queue_readiness',
        lambda queue_name, topology: {
            'tone': 'unknown',
            'show_warning': True,
            'label': 'Unverified',
            'description': f'{queue_name} worker inspection unavailable',
        },
    )
    monkeypatch.setattr(
        presentation, 'present_user_datetime', lambda value, empty: empty if value is None else str(value)
    )

    rows = presentation._queue_activity(datetime.now(UTC) - timedelta(hours=24))

    assert [row['name'] for row in rows] == ['inventory', 'maintenance']
    assert inspected == [True]
    assert all(row['active'] == 0 and row['queued'] == 0 for row in rows)
    assert all(row['posture_tone'] == 'warning' for row in rows)
    assert all(row['latest_activity'] == 'No activity' for row in rows)

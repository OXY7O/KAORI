"""Notification Deck must not probe Celery while holding an ORM read session (#3395)."""

from __future__ import annotations

import pytest
from flask import Flask

from app.common import celery_queue_health
from app.platform_operations.notifications import queries


def test_cached_topology_never_issues_broker_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(celery_queue_health, '_TOPOLOGY_CACHE', None)
    monkeypatch.setattr(celery_queue_health, 'monotonic', lambda: 100.0)

    assert celery_queue_health.get_cached_celery_topology()['status'] == 'unknown'

    observed = {
        'status': 'online',
        'worker_names': ['worker@kaori'],
        'worker_queues': {'worker@kaori': ['reports']},
        'detail': 'One worker available.',
        'error_type': None,
    }
    monkeypatch.setattr(celery_queue_health, '_TOPOLOGY_CACHE', (95.0, observed))
    recent = celery_queue_health.get_cached_celery_topology()
    assert recent['status'] == 'online'
    assert recent['worker_queues']['worker@kaori'] == ['reports']

    # An expired observation must not be presented as authoritative availability.
    monkeypatch.setattr(celery_queue_health, 'monotonic', lambda: 110.0)
    assert celery_queue_health.get_cached_celery_topology()['status'] == 'unknown'


def test_concurrent_inspection_does_not_queue_a_second_broker_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(celery_queue_health, '_TOPOLOGY_CACHE', None)
    lock = celery_queue_health._TOPOLOGY_INSPECTION_LOCK
    assert lock.acquire(blocking=False)
    try:
        # The short-circuit runs without Flask context or Celery broker access.
        result = celery_queue_health.inspect_celery_topology()
    finally:
        lock.release()
    assert result['status'] == 'unknown'


class _Field:
    def __eq__(self, _other: object) -> bool:
        return True

    def in_(self, _values: object) -> bool:
        return True

    def is_(self, _value: object) -> bool:
        return True

    def desc(self) -> _Field:
        return self


class _Query:
    def __init__(self, items: list[object]) -> None:
        self.items = items

    def filter(self, *_predicates: object) -> _Query:
        return self

    def order_by(self, *_columns: object) -> _Query:
        return self

    def limit(self, _limit: int) -> _Query:
        return self

    def options(self, *_options: object) -> _Query:
        return self

    def count(self) -> int:
        return len(self.items)

    def all(self) -> list[object]:
        return self.items


def test_queued_job_deck_renders_without_live_worker_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Notification:
        read_at = _Field()
        status = _Field()
        created_at = _Field()
        id = _Field()

    class JobExecution:
        query = _Query([object()])
        status = _Field()
        requested_by = _Field()
        updated_at = _Field()
        id = _Field()

    monkeypatch.setattr(queries, 'Notification', Notification)
    monkeypatch.setattr(queries, 'JobExecution', JobExecution)
    monkeypatch.setattr(queries, '_general_notification_query', lambda _user_id: _Query([]))
    monkeypatch.setattr(queries, '_work_inbox_query', lambda _user_id: _Query([]))
    monkeypatch.setattr(queries, 'joinedload', lambda _relationship: None)
    monkeypatch.setattr(
        queries,
        'present_job_execution',
        lambda _job: {'status': 'queued', 'queue_name': 'reports'},
    )
    observed: list[str] = []

    def cached_topology() -> dict[str, object]:
        observed.append('cache')
        return {'status': 'unknown', 'worker_names': [], 'worker_queues': {}, 'error_type': None}

    monkeypatch.setattr(queries, 'get_cached_celery_topology', cached_topology)

    app = Flask(__name__)
    app.extensions['kaori_tenant_approval_work_inbox'] = lambda **_kwargs: {
        'items': [], 'pending_count': 0, 'total_count': 0,
    }
    app.extensions['kaori_secret_reveal_approval_work_inbox'] = lambda **_kwargs: {
        'items': [], 'pending_count': 0, 'total_count': 0,
    }
    app.extensions['kaori_secret_reveal_requester_work_inbox'] = lambda **_kwargs: {
        'items': [], 'ready_count': 0, 'total_count': 0,
    }

    with app.app_context():
        snapshot = queries.get_activity_center_context(user_id=5, include_all_jobs=True)

    assert observed == ['cache']
    assert snapshot['active_jobs'][0]['queue_health']['status'] == 'unknown'
    assert snapshot['active_jobs'][0]['queue_health']['ready'] is False

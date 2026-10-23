"""Executable UAT contracts for the canonical Analytics Snapshot lifecycle (#2935).

Pure snapshots/mocks ensure no real PostgreSQL row, worker or archive object
is modified. DevContainer end-to-end and human Visual QA are separate gates.
"""
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask
from jinja2 import Environment

from app.platform_operations.data_lifecycle.retention.domains import analytics_snapshot as adapter
from app.platform_operations.data_lifecycle.service import queue_lifecycle_execution, update_lifecycle_policy
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy

ROOT = Path(__file__).resolve().parents[3]
SERVICE = 'app.platform_operations.data_lifecycle.service'
WORKSPACE = 'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html'
CUTOFF = datetime(2026, 10, 1, tzinfo=UTC)


def _snapshot(**changes: object) -> SimpleNamespace:
    values = {
        'id': 17,
        'status': 'ready',
        'updated_at': CUTOFF - timedelta(days=4),
        'payload_json': {'value': 12},
        'generated_at': CUTOFF - timedelta(days=18),
        'expires_at': CUTOFF - timedelta(days=5),
        'freshness_minutes': 20,
        'stale_grace_minutes': 60,
    }
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    ('changes', 'eligible'),
    [
        ({}, True),
        ({'status': 'pending'}, False),
        ({'updated_at': CUTOFF}, False),
        ({'updated_at': CUTOFF + timedelta(minutes=1)}, False),
        ({'expires_at': CUTOFF - timedelta(minutes=30), 'stale_grace_minutes': 120}, False),
        ({'expires_at': CUTOFF - timedelta(minutes=120), 'stale_grace_minutes': 120}, False),
        ({'expires_at': CUTOFF - timedelta(hours=4), 'stale_grace_minutes': 120}, True),
        ({'expires_at': CUTOFF + timedelta(days=1)}, False),
        ({'status': 'failed', 'payload_json': None, 'generated_at': None}, True),
    ],
)
def test_serve_window_preserves_pending_fresh_and_stale_servable(
    changes: dict[str, object], eligible: bool,
) -> None:
    assert adapter._eligible_for_boundary(_snapshot(**changes), cutoff_at=CUTOFF) is eligible


def test_serve_window_defaults_to_generated_at_plus_freshness_when_expiry_missing() -> None:
    generated = CUTOFF - timedelta(hours=5)
    snapshot = _snapshot(
        expires_at=None, generated_at=generated, freshness_minutes=30, stale_grace_minutes=240,
    )
    # 30 minutes freshness + four hours grace has expired at the cutoff.
    assert adapter._eligible_for_boundary(snapshot, cutoff_at=CUTOFF) is True
    snapshot.stale_grace_minutes = 300
    assert adapter._eligible_for_boundary(snapshot, cutoff_at=CUTOFF) is False


def test_cleanup_rechecks_rows_and_excludes_refreshed_and_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[int]] = []
    commits: list[str] = []
    rows = [
        _snapshot(id=17),
        _snapshot(id=18, updated_at=CUTOFF + timedelta(days=1)),
        _snapshot(id=19, status='pending'),
        _snapshot(
            id=20, expires_at=CUTOFF - timedelta(minutes=30), stale_grace_minutes=120,
        ),
    ]

    class Column:
        def in_(self, values: list[int]) -> list[int]:
            return list(values)

    class Query:
        def filter(self, selected_ids: list[int]) -> 'Query':
            calls.append(selected_ids)
            return self

        def all(self) -> list[SimpleNamespace]:
            return rows

        def delete(self, *, synchronize_session: bool) -> int:
            assert synchronize_session is False
            return len(calls[-1])

    monkeypatch.setattr(adapter, 'AnalyticsSnapshot', SimpleNamespace(id=Column(), query=Query()))
    monkeypatch.setattr(
        adapter, 'db', SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append('commit'))),
    )
    deleted = adapter.AnalyticsSnapshotArchiveDomain._delete_safe_batch(
        [17, 18, 19, 20], cutoff_at=CUTOFF,
    )
    assert deleted == 1
    assert calls == [[17, 18, 19, 20], [17]]
    assert commits == ['commit']


def _fake_policy(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=enabled,
        settings={},
        retention_days=30,
        archive_retention_days=180,
        batch_size=1000,
        protected_max_days=None,
    )


@pytest.mark.parametrize('mode', ['archive_only', 'archive_and_cleanup'])
def test_analytics_manual_archive_buttons_create_canonical_job_with_info_toast(mode: str) -> None:
    app = Flask(__name__)
    app.config['RETENTION_CELERY_QUEUE'] = 'maintenance'
    domain = SimpleNamespace(
        name='analytics_snapshot', cleanup_supported=True,
        build_policy=lambda: _fake_policy(enabled=True),
    )
    job = SimpleNamespace(id=27, celery_task_id='synthetic-uat-task')
    with (
        app.app_context(),
        patch(f'{SERVICE}.get_archive_domain', return_value=domain),
        patch(f'{SERVICE}.get_policy', return_value=SimpleNamespace(enabled=True)),
        patch(f'{SERVICE}.enqueue_canonical_job', return_value=(job, True)) as queue,
        patch(f'{SERVICE}.record_operational_activity', side_effect=lambda **kw: kw),
        patch(f'{SERVICE}.url_for', return_value='/test/jobs'),
    ):
        feedback = queue_lifecycle_execution(
            domain_name='analytics_snapshot', mode=mode, user_id=7,
        )

    queued = queue.call_args.kwargs
    assert queued['job_type'] == 'data_lifecycle'
    assert queued['queue_name'] == 'maintenance'
    assert queued['operation'] == mode
    assert queued['task_kwargs']['cleanup'] is (mode == 'archive_and_cleanup')
    assert queued['task_kwargs']['domain_name'] == 'analytics_snapshot'
    assert queued['resource_group'] == 'data-lifecycle:analytics_snapshot'
    assert feedback['status'] == 'info'
    assert feedback['metadata']['feedback_delivery'] == 'toast'
    assert feedback['metadata']['job_execution_id'] == 27
    assert feedback['delivery_policy'] is OperationalDeliveryPolicy.DECK_ON_FAILURE
    assert feedback['delivery_policy'].deck_visible('info') is False


def test_disabled_analytics_policy_does_not_queue_job_and_warns_in_deck() -> None:
    domain = SimpleNamespace(
        name='analytics_snapshot', cleanup_supported=True,
        build_policy=lambda: _fake_policy(enabled=False),
    )
    with (
        patch(f'{SERVICE}.get_archive_domain', return_value=domain),
        patch(f'{SERVICE}.get_policy', return_value=SimpleNamespace(enabled=False)),
        patch(f'{SERVICE}.enqueue_canonical_job') as queue,
        patch(f'{SERVICE}.record_operational_activity', side_effect=lambda **kw: kw),
        patch(f'{SERVICE}.url_for', return_value='/test/lifecycle'),
    ):
        feedback = queue_lifecycle_execution(
            domain_name='analytics_snapshot', mode='archive_only', user_id=7,
        )
    queue.assert_not_called()
    assert feedback['status'] == 'warning'
    assert feedback['delivery_policy'].deck_visible('warning') is True


def test_analytics_policy_save_is_committed_through_standard_feedback() -> None:
    domain = SimpleNamespace(
        name='analytics_snapshot', cleanup_supported=True,
        build_policy=lambda: _fake_policy(enabled=True),
    )
    with (
        patch(f'{SERVICE}.get_archive_domain', return_value=domain),
        patch(f'{SERVICE}.update_policy') as update,
        patch(f'{SERVICE}.record_operational_activity', side_effect=lambda **kw: kw),
        patch(f'{SERVICE}.url_for', return_value='/test/lifecycle'),
    ):
        feedback = update_lifecycle_policy(
            domain_name='analytics_snapshot',
            values={
                'enabled': 'on',
                'hot_retention_days': '30',
                'archive_retention_days': '180',
                'batch_size': '1000',
                'operation_mode': 'archive_only',
            },
            user_id=7,
        )
    assert update.call_args.kwargs['domain'] == 'analytics_snapshot'
    assert update.call_args.kwargs['operation_mode'] == 'archive_only'
    assert update.call_args.kwargs['enabled'] is True
    assert feedback['status'] == 'success'
    assert feedback['delivery_policy'].deck_visible('success') is False


def test_preview_is_read_only_and_all_four_actions_use_shared_ui() -> None:
    source = (ROOT / WORKSPACE).read_text(encoding='utf-8')
    Environment().parse(source)
    assert "{% if selected.name == 'analytics_snapshot' %}" in source
    assert 'Pending and still-serveable snapshots stay hot.' in source
    assert 'Archiving requires both stale grace and hot retention to have elapsed.' in source
    assert source.count('type="submit"') == 3
    assert source.count("hx-disabled-elt=\"find button[type='submit']\"") == 3
    assert source.count('name="csrf_token" value="{{ csrf_token() }}"') == 3
    assert 'name="mode" value="archive_only"' in source
    assert 'name="mode" value="archive_and_cleanup"' in source
    assert 'hx-get="{{ url_for(\'platform_operations.data_lifecycle.preview\'' in source
    assert 'hx-target="#data-lifecycle-domain-workspace"' in source

    routes = (ROOT / 'app/platform_operations/data_lifecycle/routes.py').read_text(encoding='utf-8')
    preview = routes.split('def preview()', 1)[1].split('def save_policy()', 1)[0]
    assert '_context(preview=True)' in preview
    assert 'queue_lifecycle_execution(' not in preview
    assert "if request.headers.get('HX-Request') == 'true':" in preview

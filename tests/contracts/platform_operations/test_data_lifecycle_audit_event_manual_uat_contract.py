"""Administrative Audit Events manual Archive Only UAT contracts (#2939).

Synthetic mocks only: these checks must not enqueue a real worker or mutate
AuditEvent rows, storage, scheduling, archive download or cleanup.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from app.platform_operations.data_lifecycle.retention.service import _require_audit_event_manual_admission
from app.platform_operations.data_lifecycle.service import queue_lifecycle_execution, update_lifecycle_policy
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy

ROOT = Path(__file__).resolve().parents[3]
SERVICE = 'app.platform_operations.data_lifecycle.service'
ENGINE = 'app.platform_operations.data_lifecycle.retention.service'


def _policy(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=enabled,
        retention_days=365,
        archive_retention_days=3650,
        batch_size=250,
        protected_max_days=None,
        protect_unreviewed=False,
        settings={'archive_only': True, 'manual_execution_only': True},
    )


def _requester(*, active: bool = True, admin: bool = True, source: str = 'database') -> SimpleNamespace:
    return SimpleNamespace(is_active=active, is_super_admin=admin, auth_source=source)


def test_explicit_enable_manual_archive_then_disable_preserves_safe_policy_and_feedback() -> None:
    app = Flask(__name__)
    app.config['RETENTION_CELERY_QUEUE'] = 'maintenance'
    state = {'enabled': False, 'schedule_enabled': False, 'operation_mode': 'archive_only'}
    requester = _requester()
    job = SimpleNamespace(id=27, celery_task_id='synthetic-task')

    def persist(**kw: object) -> None:
        state.update(
            enabled=bool(kw['enabled']),
            schedule_enabled=bool(kw['schedule_enabled']),
            operation_mode=str(kw['operation_mode']),
        )

    domain = SimpleNamespace(
        name='audit_event', cleanup_supported=False,
        build_policy=lambda: _policy(enabled=state['enabled']),
    )

    def save(values: dict[str, str]) -> dict:
        return update_lifecycle_policy(
            domain_name='audit_event', values=values, user_id=7,
        )

    with (
        app.app_context(),
        patch(f'{SERVICE}.db.session.get', return_value=requester),
        patch(f'{ENGINE}.db.session.get', return_value=requester),
        patch(f'{SERVICE}.get_archive_domain', return_value=domain),
        patch(f'{SERVICE}.get_policy', side_effect=lambda _name: SimpleNamespace(**state)),
        patch(f'{ENGINE}.get_policy', side_effect=lambda _name: SimpleNamespace(**state)),
        patch(f'{SERVICE}.update_policy', side_effect=persist) as update,
        patch(f'{SERVICE}.enqueue_canonical_job', return_value=(job, True)) as queue,
        patch(f'{SERVICE}.url_for', return_value='/test/lifecycle'),
        patch(f'{SERVICE}.record_operational_activity', side_effect=lambda **kw: kw),
    ):
        blocked = queue_lifecycle_execution(
            domain_name='audit_event', mode='archive_only', user_id=7,
        )
        assert blocked['status'] == 'warning'
        queue.assert_not_called()

        enabled_feedback = save({
            'enabled': 'on',
            'operation_mode': 'archive_only',
            'schedule_enabled': 'on',  # malicious form cannot enable scheduler
        })
        assert enabled_feedback['status'] == 'success'
        assert enabled_feedback['delivery_policy'] is OperationalDeliveryPolicy.DECK_ON_FAILURE
        assert enabled_feedback['delivery_policy'].deck_visible('success') is False
        assert state == {'enabled': True, 'schedule_enabled': False, 'operation_mode': 'archive_only'}
        assert update.call_args.kwargs['domain'] == 'audit_event'

        assert _require_audit_event_manual_admission(
            trigger_type='manual', triggered_by_user_id=7,
        ) is None
        queued = queue_lifecycle_execution(
            domain_name='audit_event', mode='archive_only', user_id=7,
        )
        assert queued['status'] == 'info'
        assert queued['metadata']['feedback_delivery'] == 'toast'
        assert queued['delivery_policy'].deck_visible('info') is False
        assert queue.call_args.kwargs['task_kwargs']['cleanup'] is False
        assert queue.call_args.kwargs['task_kwargs']['trigger_type'] == 'manual'
        assert queue.call_args.kwargs['task_kwargs']['requested_by_user_id'] == 7

        disabled_feedback = save({'operation_mode': 'archive_only'})
        assert disabled_feedback['status'] == 'success'
        assert state['enabled'] is False
        assert state['schedule_enabled'] is False
        with pytest.raises(PermissionError, match='persisted'):
            _require_audit_event_manual_admission(
                trigger_type='manual', triggered_by_user_id=7,
            )
        blocked_again = queue_lifecycle_execution(
            domain_name='audit_event', mode='archive_only', user_id=7,
        )
        assert blocked_again['status'] == 'warning'
        assert queue.call_count == 1


@pytest.mark.parametrize('enabled', [False, True])
def test_policy_context_resolves_saved_manual_enable_state_without_scheduler(enabled: bool) -> None:
    from app.platform_operations.data_lifecycle.retention.presentation import build_domain_retention_context

    app = Flask(__name__)
    domain = SimpleNamespace(
        name='audit_event', source_model='audit_events',
        build_policy=lambda: _policy(enabled=enabled),
    )
    stored = SimpleNamespace(
        enabled=enabled, schedule_enabled=True, operation_mode='archive_and_cleanup',
    )
    jobs = MagicMock()
    jobs.query.filter.return_value.count.return_value = 0
    with (
        app.app_context(),
        patch(
            'app.platform_operations.data_lifecycle.retention.presentation._can_govern_audit_event',
            return_value=True,
        ),
        patch(
            'app.platform_operations.data_lifecycle.retention.presentation.get_archive_domain',
            return_value=domain,
        ),
        patch(
            'app.platform_operations.data_lifecycle.retention.presentation._build_archive_posture',
            return_value={'active_count': 0},
        ),
        patch(
            'app.platform_operations.data_lifecycle.retention.presentation._cached_status',
            return_value={'queue_ready': True, 'label': 'Online'},
        ),
        patch('app.platform_operations.data_lifecycle.retention.presentation.JobExecution', jobs),
    ):
        context = build_domain_retention_context(
            'audit_event', policy=_policy(enabled=enabled), stored_policy=stored,
        )
    assert context['enabled'] is enabled
    assert context['operation_mode'] == 'archive_only'
    assert context['schedule_enabled'] is False
    assert context['active_lifecycle_jobs'] == 0
    assert context['domain'] == 'audit_event'


def test_cleanup_request_is_rejected_before_dispatch_even_when_enabled() -> None:
    domain = SimpleNamespace(name='audit_event', cleanup_supported=False)
    with (
        patch(f'{SERVICE}.db.session.get', return_value=_requester()),
        patch(f'{SERVICE}.get_archive_domain', return_value=domain),
        patch(f'{SERVICE}.enqueue_canonical_job') as queue,
        patch(f'{SERVICE}.record_operational_activity', side_effect=lambda **kw: kw),
        patch(f'{SERVICE}.url_for', return_value='/test/lifecycle'),
    ):
        feedback = queue_lifecycle_execution(
            domain_name='audit_event', mode='archive_and_cleanup', user_id=7,
        )
        assert feedback['status'] == 'warning'
        assert feedback['metadata']['reason'] == 'cleanup_not_admitted'
        assert feedback['delivery_policy'].deck_visible('warning') is True
        queue.assert_not_called()


@pytest.mark.parametrize('active,admin,source', [
    (False, True, 'database'),
    (True, False, 'database'),
    (True, True, 'ldap'),
])
def test_unapproved_requester_cannot_enable_audit_policy(
    active: bool, admin: bool, source: str,
) -> None:
    with patch(f'{SERVICE}.db.session.get', return_value=_requester(
        active=active, admin=admin, source=source,
    )), patch(f'{SERVICE}.update_policy') as write:
        with pytest.raises(PermissionError, match='authorized local Super Admin'):
            update_lifecycle_policy(
                domain_name='audit_event',
                values={'enabled': 'on', 'operation_mode': 'archive_only'},
                user_id=7,
            )
        write.assert_not_called()


def test_interface_distinguishes_paused_and_manual_archive_ready_with_no_other_actions() -> None:
    workspace = (ROOT / 'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    text = workspace.read_text(encoding='utf-8')
    assert "selected.name == 'audit_event'" in text
    assert "selected.name not in ('notification_delivery', 'audit_event')" in text
    assert 'AuditEvent archive policy paused by default.' in text
    assert 'Manual Archive Only enabled.' in text
    assert 'Disable the policy after UAT.' in text
    assert 'role="status"' in text
    assert '{% if execution_blocked %}disabled{% endif %}' in text
    assert 'name="enabled"' in text
    assert 'name="mode" value="archive_only"' in text
    assert "components/operation_feedback_oob.html" in text
    source = (ROOT / 'app/platform_operations/data_lifecycle/retention/presentation.py').read_text(
        encoding='utf-8',
    )
    assert "'audit_event': 'Source-owned administrative AuditEvent evidence; manual Archive Only.'" in source
    assert 'Manual Archive Only; paused by default. Separate from Activity Register' in source
    assert 'Retention/RBAC review pending.' in source


def test_preview_remains_read_only_and_archive_download_bypass_stays_blocked() -> None:
    routes = (ROOT / 'app/platform_operations/data_lifecycle/routes.py').read_text(encoding='utf-8')
    preview = routes.split('def preview()', 1)[1].split('def save_policy()', 1)[0]
    assert '_context(preview=True)' in preview
    assert 'queue_lifecycle_execution(' not in preview
    assert 'update_lifecycle_policy(' not in preview
    assert "if request.headers.get('HX-Request') == 'true':" in preview
    assert "if value == 'audit_event' and not (" in routes
    assert "abort(403, description='Source-specific archive export has not been admitted.')" in routes

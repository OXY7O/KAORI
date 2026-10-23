"""Fail-closed AuditEvent archive-only admission and source separation (#2890).

These tests do not archive, purge, or mutate any real audit record. A
PostgreSQL/worker/Archive Storage UAT is independently required.
"""
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask
from werkzeug.exceptions import Forbidden

from app.platform_operations.data_lifecycle.retention.domains.audit_event import AuditEventArchiveDomain

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_audit_event_archive_uses_minimal_redacted_evidence_without_actor_inference() -> None:
    event = SimpleNamespace(
        id=19,
        actor_user_id=None,
        target_type='job_execution',
        target_id='job-45',
        action='automatic_job_succeeded',
        summary='Completed; token=abc123 password=unsafe',
        created_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        metadata_json={'api_key': 'secret', 'custom': {'bearer': 'secret'}},
        ip_address='192.0.2.10',
        user_agent='private-browser',
    )
    archive = AuditEventArchiveDomain()._serialize(event)
    assert archive['domain'] == 'audit_event'
    assert archive['source'] == {'model': 'audit_events', 'record_id': 19}
    evidence = archive['evidence']
    assert evidence['actor_user_id'] is None
    assert evidence['actor_identity_is_snapshot'] is False
    assert evidence['source_permission_admission_pending'] is True
    assert evidence['created_at'] == '2026-09-01T08:00:00+00:00'
    assert 'abc123' not in evidence['summary']
    assert 'unsafe' not in evidence['summary']
    assert 'metadata_json' not in str(archive)
    assert '192.0.2.10' not in str(archive)
    assert 'private-browser' not in str(archive)


def test_audit_event_archive_adapter_is_preview_first_paused_and_never_deletes_hot_rows() -> None:
    s = read('app/platform_operations/data_lifecycle/retention/domains/audit_event.py')
    registry = read('app/platform_operations/data_lifecycle/retention/domains/__init__.py')
    engine = read('app/platform_operations/data_lifecycle/retention/service.py')
    assert "name = 'audit_event'" in s
    assert "source_model = 'audit_events'" in s
    assert "enabled=False" in s
    assert "cleanup_supported = False" in s
    assert "'audit_event': AuditEventArchiveDomain" in registry
    assert 'AuditEvent.created_at < cutoff_at' in s
    assert 'AuditEvent.id <= boundary.maximum_record_id' in s
    assert 'AuditEvent.id > last_id' in s
    assert '.limit(policy.batch_size)' in s
    assert 'raise RuntimeError(' in s.split('def cleanup_records(', 1)[1]
    assert 'db.session.commit()' not in s
    assert 'AuditEvent.query.delete(' not in s
    assert "if cleanup and not getattr(domain, 'cleanup_supported', True):" in engine
    assert "if domain.name == 'audit_event':" in engine
    assert '_require_audit_event_manual_admission(' in engine


def test_policy_schedule_cleanup_and_archive_export_fail_closed_for_audit_event() -> None:
    admission = read('app/platform_operations/data_lifecycle/service.py')
    worker = read('app/platform_operations/data_lifecycle/retention/tasks.py')
    engine = read('app/platform_operations/data_lifecycle/retention/service.py')
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    history = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')
    ui = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    routes = read('app/platform_operations/data_lifecycle/routes.py')

    assert "domain_name not in {'notification_delivery', 'audit_event'}" in admission
    assert "'cleanup_not_admitted'" in admission
    assert "if domain_name in {'notification_delivery', 'audit_event'}:" in presentation
    assert "selected.name not in ('notification_delivery', 'audit_event')" in ui
    assert 'Archive Only: administrative AuditEvent evidence stays in PostgreSQL' in ui
    assert "if domain_name == 'audit_event':" in worker
    assert "'scheduling_not_admitted'" in worker
    assert "'archive_purge'] = {'status': 'not_admitted'" in worker
    assert "if domain_name == 'audit_event' and not dry_run:" in engine
    assert "if artifact.domain == 'audit_event':" in engine
    assert "raise PermissionError(" in engine
    assert "archive.domain != 'audit_event'" in history
    assert 'except PermissionError:' in routes
    assert "abort(403, description='Source-specific archive export has not been admitted.')" in routes



def test_disabled_audit_event_policy_explains_manual_safe_uat_without_enabling_cleanup() -> None:
    ui = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    service = read('app/platform_operations/data_lifecycle/service.py')
    adapter = read('app/platform_operations/data_lifecycle/retention/domains/audit_event.py')
    assert "if selected.name == 'audit_event'" in ui
    assert 'AuditEvent archive policy paused by default.' in ui
    assert 'Preview remains read-only.' in ui
    assert 'Policy enabled and Save Policy, then run Archive Only manually.' in ui
    assert 'Saving does not start a job; scheduling, hot cleanup, archive download, and purge stay blocked.' in ui
    assert 'name="enabled"' in ui
    assert "selected.name not in ('notification_delivery', 'audit_event')" in ui
    assert "'archive_only'" in service
    assert "cleanup_supported = False" in adapter
    assert "enabled=False" in adapter



def test_audit_events_are_not_conflated_with_notifications_or_tenant_audit_evidence() -> None:
    source = read('app/access/activity_audit/administrative_sources.py')
    policy = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    docs = read('app/platform_operations/data_lifecycle/retention/README.md')
    assert 'from app.models.audit import AuditEvent' in source
    assert "source_model = 'audit_events'" in read(
        'app/platform_operations/data_lifecycle/retention/domains/audit_event.py'
    )
    assert "'audit_event': 'Administrative Audit Events'" in policy
    assert "'operational_activity': 'Activity Audit'" in policy
    assert "'tenant_audit_evidence': 'Tenant Audit Evidence'" in policy
    assert 'source-owned' in docs


def test_audit_event_scope_and_hot_history_counts_are_super_admin_only() -> None:
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    service = read('app/platform_operations/data_lifecycle/service.py')
    routes = read('app/platform_operations/data_lifecycle/routes.py')
    engine = read('app/platform_operations/data_lifecycle/retention/service.py')
    model = read('app/models/user.py')

    assert "getattr(current_user, 'is_super_admin', False)" in presentation
    assert "getattr(current_user, 'auth_source', None) == 'database'" in presentation
    assert "name for name in DOMAIN_FACTORIES if name != 'audit_event' or allowed_audit_event" in presentation
    assert "if selected_domain == 'audit_event' and not allowed_audit_event:" in presentation
    assert "if archive_domain == 'audit_event' and not allowed_audit_event:" in presentation
    assert "exclude_domains=() if allowed_audit_event else ('audit_event',)" in presentation
    assert "ArchiveArtifact.domain.notin_(exclude_domains)" in engine
    assert "if value == 'audit_event' and not (" in routes
    assert "def _check_audit_event_governance(domain_name: str, user_id: int)" in service
    assert "user is None or not user.is_active" in service
    assert "not user.is_super_admin or user.auth_source != 'database':" in service
    assert service.count("_check_audit_event_governance(domain_name, user_id)") == 2
    assert "is_super_admin: Mapped[bool]" in model


@pytest.mark.parametrize(
    ('super_admin', 'source', 'expected'),
    [
        (False, 'database', False),
        (True, 'ldap', False),
        (True, 'database', True),
    ],
)
def test_audit_event_access_requires_authorized_local_super_admin(
    super_admin: bool, source: str, expected: bool,
) -> None:
    from app.platform_operations.data_lifecycle.retention.presentation import _can_govern_audit_event

    user = SimpleNamespace(is_authenticated=True, is_super_admin=super_admin, auth_source=source)
    with patch('app.platform_operations.data_lifecycle.retention.presentation.current_user', user):
        assert _can_govern_audit_event() is expected


def test_audit_event_post_domain_rejects_non_super_admin_before_queueing() -> None:
    from app.platform_operations.data_lifecycle.routes import _mutation_domain

    app = Flask(__name__)
    with app.test_request_context(
        '/platform-operations/data-lifecycle/run',
        method='POST',
        data={'domain': 'audit_event'},
    ):
        with patch(
            'app.platform_operations.data_lifecycle.routes.current_user',
            SimpleNamespace(is_super_admin=False, auth_source='database'),
        ):
            with pytest.raises(Forbidden):
                _mutation_domain()
        with patch(
            'app.platform_operations.data_lifecycle.routes.current_user',
            SimpleNamespace(is_super_admin=True, auth_source='database'),
        ):
            assert _mutation_domain() == 'audit_event'


def test_audit_event_source_security_matrix_remains_incomplete_and_export_fail_closed() -> None:
    matrix = read('docs/architecture/audit-event-producer-security-retention-matrix.md')
    index = read('docs/architecture/README.md')
    uat = read('docs/operations/audit-event-data-lifecycle-devcontainer-uat.md')
    archive = read('app/platform_operations/data_lifecycle/retention/domains/audit_event.py')
    engine = read('app/platform_operations/data_lifecycle/retention/service.py')
    for confirmed_source in (
        'app/common/admin_audit.py',
        'app/platform_operations/jobs/audit.py',
        'app/kubernetes/tenant/audit.py',
        'app/kubernetes/governance/tls_certificates/audit.py',
    ):
        assert confirmed_source in matrix
    assert 'not exhaustive' in matrix
    assert 'retention' in matrix
    assert 'legal holds' in matrix
    assert 'unknown producer' in matrix
    assert 'audit-event-producer-security-retention-matrix.md' in index
    assert 'audit-event-producer-security-retention-matrix.md' in uat
    assert 'cleanup_supported = False' in archive
    assert "if artifact.domain == 'audit_event':" in engine
    assert "if domain_name == 'audit_event' and not dry_run:" in engine


def test_audit_event_engine_rechecks_authorization_before_lock_or_archive_write() -> None:
    from app.platform_operations.data_lifecycle.retention.service import run_retention_archive

    domain = SimpleNamespace(
        name='audit_event',
        cleanup_supported=False,
        build_policy=lambda: SimpleNamespace(enabled=True),
    )
    with (
        patch(
            'app.platform_operations.data_lifecycle.retention.service.get_archive_domain',
            return_value=domain,
        ),
        patch(
            'app.platform_operations.data_lifecycle.retention.service._require_audit_event_manual_admission',
            side_effect=PermissionError('revoked'),
        ) as admission,
        patch('app.platform_operations.data_lifecycle.retention.service.retention_lock') as lock,
    ):
        with pytest.raises(PermissionError, match='revoked'):
            run_retention_archive(
                domain_name='audit_event',
                trigger_type='manual',
                cleanup=False,
                triggered_by_user_id=27,
            )
        admission.assert_called_once_with(trigger_type='manual', triggered_by_user_id=27)
        lock.assert_not_called()


@pytest.mark.parametrize(
    ('trigger', 'requester_id', 'policy_enabled', 'operation_mode', 'scheduled', 'active', 'admin', 'source'),
    [
        ('cli', None, True, 'archive_only', False, True, True, 'database'),
        ('scheduled', 27, True, 'archive_only', False, True, True, 'database'),
        ('manual', None, True, 'archive_only', False, True, True, 'database'),
        ('manual', 27, False, 'archive_only', False, True, True, 'database'),
        ('manual', 27, True, 'archive_and_cleanup', False, True, True, 'database'),
        ('manual', 27, True, 'archive_only', True, True, True, 'database'),
        ('manual', 27, True, 'archive_only', False, False, True, 'database'),
        ('manual', 27, True, 'archive_only', False, True, False, 'database'),
        ('manual', 27, True, 'archive_only', False, True, True, 'ldap'),
    ],
)
def test_audit_event_worker_denies_unapproved_trigger_policy_and_revoked_requester(
    trigger: str,
    requester_id: int | None,
    policy_enabled: bool,
    operation_mode: str,
    scheduled: bool,
    active: bool,
    admin: bool,
    source: str,
) -> None:
    from app.platform_operations.data_lifecycle.retention.service import _require_audit_event_manual_admission

    stored = SimpleNamespace(
        enabled=policy_enabled, operation_mode=operation_mode, schedule_enabled=scheduled,
    )
    user = SimpleNamespace(is_active=active, is_super_admin=admin, auth_source=source)
    with (
        patch('app.platform_operations.data_lifecycle.retention.service.get_policy', return_value=stored),
        patch('app.platform_operations.data_lifecycle.retention.service.db.session.get', return_value=user),
    ):
        with pytest.raises(PermissionError):
            _require_audit_event_manual_admission(
                trigger_type=trigger,
                triggered_by_user_id=requester_id,
            )


def test_audit_event_worker_admits_only_active_local_admin_with_saved_manual_policy() -> None:
    from app.platform_operations.data_lifecycle.retention.service import _require_audit_event_manual_admission

    policy = SimpleNamespace(
        enabled=True, operation_mode='archive_only', schedule_enabled=False,
    )
    requester = SimpleNamespace(is_active=True, is_super_admin=True, auth_source='database')
    with (
        patch('app.platform_operations.data_lifecycle.retention.service.get_policy', return_value=policy),
        patch('app.platform_operations.data_lifecycle.retention.service.db.session.get', return_value=requester),
    ):
        assert _require_audit_event_manual_admission(
            trigger_type='manual', triggered_by_user_id=27,
        ) is None


def test_audit_event_worker_missing_policy_or_deleted_requester_fails_closed() -> None:
    from app.platform_operations.data_lifecycle.retention.service import _require_audit_event_manual_admission

    valid_policy = SimpleNamespace(
        enabled=True, operation_mode='archive_only', schedule_enabled=False,
    )
    with (
        patch('app.platform_operations.data_lifecycle.retention.service.get_policy', return_value=None),
        patch('app.platform_operations.data_lifecycle.retention.service.db.session.get') as lookup,
    ):
        with pytest.raises(PermissionError, match='persisted'):
            _require_audit_event_manual_admission(
                trigger_type='manual', triggered_by_user_id=27,
            )
        lookup.assert_not_called()

    with (
        patch('app.platform_operations.data_lifecycle.retention.service.get_policy', return_value=valid_policy),
        patch('app.platform_operations.data_lifecycle.retention.service.db.session.get', return_value=None),
    ):
        with pytest.raises(PermissionError, match='active'):
            _require_audit_event_manual_admission(
                trigger_type='manual', triggered_by_user_id=27,
            )


def test_direct_archive_verify_rejects_unapproved_audit_event_before_integrity_io() -> None:
    from app.platform_operations.data_lifecycle.service import verify_lifecycle_archive

    archive = SimpleNamespace(domain='audit_event')
    with (
        patch('app.platform_operations.data_lifecycle.service.db.session.get', return_value=archive),
        patch(
            'app.platform_operations.data_lifecycle.service._check_audit_event_governance',
            side_effect=PermissionError('source denied'),
        ) as governance,
        patch('app.platform_operations.data_lifecycle.service.verify_archive_artifact') as verify,
    ):
        with pytest.raises(PermissionError, match='source denied'):
            verify_lifecycle_archive(archive_id='synthetic-archive-uuid', user_id=27)
        governance.assert_called_once_with('audit_event', 27)
        verify.assert_not_called()


def test_direct_audit_archive_verify_route_returns_403_instead_of_leaking_details() -> None:
    routes = read('app/platform_operations/data_lifecycle/routes.py')
    service = read('app/platform_operations/data_lifecycle/service.py')
    assert "except PermissionError:" in routes.split('def verify(archive_id:', 1)[1].split(
        "def download(archive_id:", 1,
    )[0]
    assert "abort(403, description='AuditEvent source verification access is not admitted.')" in routes
    assert 'artifact = db.session.get(ArchiveArtifact, archive_id)' in service
    assert '_check_audit_event_governance(artifact.domain, user_id)' in service

"""Runtime admission contracts for all registered Data Lifecycle adapters (#2906).

Only mocks / zero-eligible boundaries are used. No actual archive is written,
no hot record deleted, no archive object removed, and no task dispatched.
"""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.platform_operations.data_lifecycle.retention.domains import DOMAIN_FACTORIES
from app.platform_operations.data_lifecycle.retention.service import (
    purge_expired_archives,
    run_retention_archive,
)

EXPECTED_DOMAINS = {
    'operational_activity',
    'job_execution',
    'runtime_observation',
    'analytics_snapshot',
    'generated_report',
    'alert_incident',
    'tenant_audit_evidence',
    'notification_delivery',
    'audit_event',
}


def _fake_domain(domain_name: str):
    return SimpleNamespace(
        name=domain_name,
        cleanup_supported=True,
        build_policy=lambda: SimpleNamespace(enabled=True),
        inspect_boundary=lambda _policy: SimpleNamespace(
            record_count=0, maximum_record_id=None,
        ),
    )


def test_full_lifecycle_roster_is_registered_before_admission_matrix() -> None:
    assert set(DOMAIN_FACTORIES) == EXPECTED_DOMAINS


@pytest.mark.parametrize('domain_name', sorted(EXPECTED_DOMAINS))
def test_direct_engine_requires_persisted_policy_across_every_domain(domain_name: str) -> None:
    with (
        patch(
            'app.platform_operations.data_lifecycle.retention.service.get_archive_domain',
            return_value=_fake_domain(domain_name),
        ),
        patch('app.platform_operations.data_lifecycle.retention.service.get_policy', return_value=None),
        patch('app.platform_operations.data_lifecycle.retention.service.retention_lock') as lock,
    ):
        with pytest.raises(RuntimeError, match='persisted retention policy'):
            run_retention_archive(
                domain_name=domain_name, trigger_type='cli', cleanup=False,
            )
        lock.assert_not_called()


@pytest.mark.parametrize('domain_name', sorted(EXPECTED_DOMAINS))
def test_direct_engine_refuses_disabled_persisted_policy(domain_name: str) -> None:
    with (
        patch(
            'app.platform_operations.data_lifecycle.retention.service.get_archive_domain',
            return_value=_fake_domain(domain_name),
        ),
        patch(
            'app.platform_operations.data_lifecycle.retention.service.get_policy',
            return_value=SimpleNamespace(enabled=False),
        ),
        patch('app.platform_operations.data_lifecycle.retention.service.retention_lock') as lock,
    ):
        with pytest.raises(RuntimeError, match='disabled'):
            run_retention_archive(
                domain_name=domain_name, trigger_type='cli', cleanup=False,
            )
        lock.assert_not_called()


@pytest.mark.parametrize(
    ('trigger', 'scheduled', 'operation_mode'),
    [
        ('scheduled', False, 'archive_only'),
        ('worker', False, 'archive_only'),
        ('manual', True, 'archive_only'),
        ('cli', True, 'archive_only'),
        ('manual', False, 'archive_and_cleanup'),
        ('cli', False, 'archive_and_cleanup'),
    ],
)
def test_delivery_manual_archive_only_gate_precedes_archive_lock(
    trigger: str, scheduled: bool, operation_mode: str,
) -> None:
    stored = SimpleNamespace(
        enabled=True, schedule_enabled=scheduled, operation_mode=operation_mode,
    )
    with (
        patch(
            'app.platform_operations.data_lifecycle.retention.service.get_archive_domain',
            return_value=_fake_domain('notification_delivery'),
        ),
        patch('app.platform_operations.data_lifecycle.retention.service.get_policy', return_value=stored),
        patch('app.platform_operations.data_lifecycle.retention.service.retention_lock') as lock,
    ):
        with pytest.raises(RuntimeError, match='manual Archive Only'):
            run_retention_archive(
                domain_name='notification_delivery', trigger_type=trigger, cleanup=False,
            )
        lock.assert_not_called()


@pytest.mark.parametrize('trigger', ['manual', 'cli'])
def test_delivery_safe_zero_record_manual_archive_path_remains_available(trigger: str) -> None:
    stored = SimpleNamespace(
        enabled=True, schedule_enabled=False, operation_mode='archive_only',
    )
    with (
        patch(
            'app.platform_operations.data_lifecycle.retention.service.get_archive_domain',
            return_value=_fake_domain('notification_delivery'),
        ),
        patch('app.platform_operations.data_lifecycle.retention.service.get_policy', return_value=stored),
        patch(
            'app.platform_operations.data_lifecycle.retention.service.retention_lock',
            return_value=nullcontext(),
        ),
    ):
        result = run_retention_archive(
            domain_name='notification_delivery', trigger_type=trigger, cleanup=False,
        )
    assert result['status'] == 'no_data'
    assert result['record_count'] == 0


@pytest.mark.parametrize('domain_name', ['notification_delivery', 'audit_event'])
def test_archive_purge_denied_at_shared_service_boundary(domain_name: str) -> None:
    with pytest.raises(RuntimeError, match='purge'):
        purge_expired_archives(domain_name=domain_name, retention_days=1, dry_run=False)


def test_worker_and_scheduler_bypass_checks_are_shared_by_both_paused_domains() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    worker = (root / 'app/platform_operations/data_lifecycle/retention/tasks.py').read_text(encoding='utf-8')
    service = (root / 'app/platform_operations/data_lifecycle/retention/service.py').read_text(encoding='utf-8')
    assert worker.count("if domain_name in {'audit_event', 'notification_delivery'}:") >= 2
    assert "'scheduling_not_admitted'" in worker
    assert "'archive_purge'] = {'status': 'not_admitted'" in worker
    assert "if domain_name == 'notification_delivery' and not dry_run:" in service

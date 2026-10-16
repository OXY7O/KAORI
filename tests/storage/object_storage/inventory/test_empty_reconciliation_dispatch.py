from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.storage.object_storage.inventory import job_adapter


@pytest.mark.parametrize(
    ('trigger', 'actor', 'confirmation', 'phrase'),
    [
        ('scheduled', 7, 'confirm', 'CONFIRM EMPTY'),
        ('manual', None, 'confirm', 'CONFIRM EMPTY'),
        ('manual', 7, 'confirm', 'invalid'),
        ('manual', 7, 'invalid', 'CONFIRM EMPTY'),
    ],
)
def test_empty_reconciliation_dispatch_requires_explicit_authenticated_manual_authority(
    monkeypatch,
    trigger,
    actor,
    confirmation,
    phrase,
) -> None:
    def forbidden(**_kwargs):
        pytest.fail('Unsafe request must never enqueue provider inventory sync')

    monkeypatch.setattr(job_adapter, 'enqueue_all_object_storage_inventory_sync', forbidden)
    result = job_adapter.dispatch_object_storage_inventory_sync(
        requested_by_user_id=actor,
        trigger_type=trigger,
        parameters={
            'empty_reconciliation': confirmation,
            'confirmation_phrase': phrase,
            'confirm_empty_system_id': 'storage-1',
        },
    )
    assert result.status == 'blocked'


def test_scoped_empty_reconciliation_dispatch_forwards_exact_selected_id(monkeypatch) -> None:
    calls: list[dict] = []

    def enqueue(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(id=123), True

    monkeypatch.setattr(job_adapter, 'enqueue_all_object_storage_inventory_sync', enqueue)
    result = job_adapter.dispatch_object_storage_inventory_sync(
        requested_by_user_id=7,
        trigger_type='manual',
        parameters={
            'empty_reconciliation': 'confirm',
            'confirmation_phrase': 'CONFIRM EMPTY',
            'confirm_empty_system_id': 'storage-1',
        },
    )
    assert result.status == 'queued'
    assert calls == [
        {
            'requested_by_user_id': 7,
            'trigger_type': 'manual',
            'confirm_empty_system_id': 'storage-1',
        }
    ]


def test_existing_scheduled_inventory_remains_normal_without_reconciliation(monkeypatch) -> None:
    calls: list[dict] = []

    def enqueue(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(id=12), True

    monkeypatch.setattr(job_adapter, 'enqueue_all_object_storage_inventory_sync', enqueue)
    result = job_adapter.dispatch_object_storage_inventory_sync(
        requested_by_user_id=None,
        trigger_type='scheduled',
    )
    assert result.status == 'queued'
    assert calls[0]['confirm_empty_system_id'] is None


def test_confirmed_empty_action_reuses_protected_job_configuration_and_csrf() -> None:
    root = Path(__file__).resolve().parents[4]
    job_routes = (root / 'app/platform_operations/jobs/routes.py').read_text(encoding='utf-8')
    template = (
        root / 'app/templates/platform_operations/jobs/configuration/definitions/object_storage_inventory_sync.html'
    ).read_text(encoding='utf-8')
    tasks = (root / 'app/storage/object_storage/inventory/tasks.py').read_text(encoding='utf-8')
    sync_jobs = (root / 'app/storage/object_storage/inventory/sync_jobs.py').read_text(encoding='utf-8')
    assert "@permission_required('jobs.execute')" in job_routes
    assert 'current_user.has_permission(domain_permission)' in job_routes
    assert "job_key == 'object_storage.inventory.sync'" in job_routes
    assert 'parameters=empty_parameters' in job_routes
    assert 'manual_form.hidden_tag()' in template
    assert 'selected_job.empty_reconciliation_targets' in template
    assert 'name="confirm_empty_system_id"' in template
    assert 'name="confirmation_phrase"' in template
    assert 'CONFIRM EMPTY' in template
    assert "resource_group='object-storage-inventory:global'" in sync_jobs
    assert 'targets = [target]' in sync_jobs
    assert 'empty_reconciliation_evidence' in tasks

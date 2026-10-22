"""Vault JobExecution admission contracts without live provider access."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.secrets_management.secrets_pki import sync_jobs
from app.platform_operations.jobs.registry import get_job_definition


def test_registered_vault_inventory_job_is_safe_by_default():
    job = get_job_definition('secrets_pki.inventory.sync')
    assert job.domain == 'Secrets & PKI'
    assert job.queue_name == 'inventory'
    assert job.default_enabled is False
    assert job.configure_permission == 'integrations.manage'
    assert job.execute_permission == 'jobs.execute'
    assert job.domain_execute_permission == 'integrations.manage'


def test_admission_never_enqueues_mount_paths_or_secret_credentials(monkeypatch):
    def fake_dispatch(**kwargs):
        return kwargs, True

    monkeypatch.setattr(sync_jobs, 'build_vault_inventory_targets', lambda: [
        {'integration_instance_id': 15},
    ])
    monkeypatch.setattr(sync_jobs, 'enqueue_canonical_job', fake_dispatch)
    dispatched, created = sync_jobs.enqueue_vault_inventory_sync(
        requested_by_user_id=9, trigger_type='manual',
    )
    assert created is True
    assert dispatched['queue_name'] == 'inventory'
    assert dispatched['task_kwargs']['targets'] == [{'integration_instance_id': 15}]
    assert dispatched['dispatch_options'].require_registered_worker is True
    assert dispatched['max_attempts'] == 1
    serialized = repr(dispatched['task_kwargs']) + repr(dispatched['payload'])
    for disallowed in ('secret_id', 'client_token', 'mount', 'path', 'kv2_data'):
        assert disallowed not in serialized


def test_no_approved_targets_does_not_dispatch(monkeypatch):
    monkeypatch.setattr(sync_jobs, 'build_vault_inventory_targets', lambda: [])
    with pytest.raises(sync_jobs.NoEligibleVaultInventoryTargets):
        sync_jobs.enqueue_vault_inventory_sync(
            requested_by_user_id=9, trigger_type='manual',
        )


def test_only_ready_enabled_vaults_with_explicit_scopes_are_eligible(monkeypatch):
    def instance(number, *, ready=True, enabled=True, mounts=('secret',)):
        identity = SimpleNamespace(
            id=number, integration_type='secrets_pki', provider_key='vault',
            enabled=enabled, lifecycle_status='active',
            readiness_status='ready' if ready else 'validation_required',
        )
        return SimpleNamespace(id=number, integration_instance=identity, kv2_mounts=list(mounts))

    class Query:
        def order_by(self, *_):
            return self

        def limit(self, *_):
            return self

        def all(self):
            return [
                instance(1), instance(2, ready=False), instance(3, enabled=False),
                instance(4, mounts=()), instance(5, mounts=('team-kv',)),
            ]

    monkeypatch.setattr(sync_jobs, 'VaultInstance', SimpleNamespace(
        id=SimpleNamespace(asc=lambda: None), query=Query(),
    ))
    assert sync_jobs.build_vault_inventory_targets() == [
        {'integration_instance_id': 1}, {'integration_instance_id': 5},
    ]

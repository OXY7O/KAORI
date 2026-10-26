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
    assert job.domain_execute_permission == 'secrets_pki.sync'


def test_admission_never_enqueues_mount_paths_or_secret_credentials(monkeypatch):
    def fake_dispatch(**kwargs):
        return kwargs, True

    monkeypatch.setattr(
        sync_jobs,
        'build_vault_inventory_targets',
        lambda: [
            {'integration_instance_id': 15},
        ],
    )
    monkeypatch.setattr(sync_jobs, 'enqueue_canonical_job', fake_dispatch)
    dispatched, created = sync_jobs.enqueue_vault_inventory_sync(
        requested_by_user_id=9,
        trigger_type='manual',
    )
    assert created is True
    assert dispatched['queue_name'] == 'inventory'
    assert dispatched['task_kwargs']['targets'] == [{'integration_instance_id': 15}]
    assert dispatched['dispatch_options'].require_registered_worker is True
    assert dispatched['dispatch_options'].soft_time_limit_seconds == 1740
    assert dispatched['dispatch_options'].hard_time_limit_seconds == 1800
    assert dispatched['max_attempts'] == 1
    serialized = repr(dispatched['task_kwargs']) + repr(dispatched['payload'])
    for disallowed in ('secret_id', 'client_token', 'mount', 'path', 'kv2_data'):
        assert disallowed not in serialized


def test_no_approved_targets_does_not_dispatch(monkeypatch):
    monkeypatch.setattr(sync_jobs, 'build_vault_inventory_targets', lambda: [])
    with pytest.raises(sync_jobs.NoEligibleVaultInventoryTargets):
        sync_jobs.enqueue_vault_inventory_sync(
            requested_by_user_id=9,
            trigger_type='manual',
        )


def test_only_ready_enabled_vaults_with_explicit_scopes_are_eligible(monkeypatch):
    def instance(number, *, ready=True, enabled=True, mounts=('secret',)):
        identity = SimpleNamespace(
            id=number,
            integration_type='secrets_pki',
            provider_key='vault',
            enabled=enabled,
            lifecycle_status='active',
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
                instance(1),
                instance(2, ready=False),
                instance(3, enabled=False),
                instance(4, mounts=()),
                instance(5, mounts=('team-kv',)),
            ]

    monkeypatch.setattr(
        sync_jobs,
        'VaultInstance',
        SimpleNamespace(
            id=SimpleNamespace(asc=lambda: None),
            query=Query(),
        ),
    )
    assert sync_jobs.build_vault_inventory_targets() == [
        {'integration_instance_id': 1},
        {'integration_instance_id': 5},
    ]


def test_malformed_mount_configuration_is_not_eligible(monkeypatch):
    identity = SimpleNamespace(
        id=91,
        integration_type='secrets_pki',
        provider_key='vault',
        enabled=True,
        lifecycle_status='active',
        readiness_status='ready',
    )
    instance = SimpleNamespace(id=1, integration_instance=identity, kv2_mounts=['../unsafe'])

    class Query:
        def order_by(self, *_):
            return self

        def limit(self, *_):
            return self

        def all(self):
            return [instance]

    monkeypatch.setattr(
        sync_jobs,
        'VaultInstance',
        SimpleNamespace(
            id=SimpleNamespace(asc=lambda: None),
            query=Query(),
        ),
    )
    assert sync_jobs.build_vault_inventory_targets() == []


def test_one_successful_mount_and_one_failed_mount_is_partial(monkeypatch):
    from app.integrations.secrets_management.secrets_pki import tasks

    contexts = []

    class FakeContext:
        def __init__(self, *_):
            contexts.append(self)
            self.status = None
            self.partial = False

        def start(self, **kwargs):
            return None

        def checkpoint(self, **kwargs):
            return None

        def fail(self, *args, **kwargs):
            self.status = 'failed'

        def succeed(self, *, result_summary, result_type, partial):
            self.status = 'succeeded'
            self.partial = partial

        def canceled(self):
            self.status = 'canceled'

    identity = SimpleNamespace(
        integration_type='secrets_pki',
        provider_key='vault',
        enabled=True,
        lifecycle_status='active',
        readiness_status='ready',
    )
    instance = SimpleNamespace(integration_instance=identity, kv2_mounts=['first', 'second'])
    monkeypatch.setattr(
        tasks,
        'VaultInstance',
        SimpleNamespace(
            query=SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(first=lambda: instance)),
        ),
    )
    monkeypatch.setattr(tasks, 'JobExecutionContext', FakeContext)
    monkeypatch.setattr(tasks, 'build_client', lambda _instance: object())
    monkeypatch.setattr(
        tasks,
        'collect_kv2_metadata',
        lambda _client, *, mount: (
            SimpleNamespace(mount=mount)
            if mount == 'first'
            else (_ for _ in ()).throw(ValueError('simulated provider failure'))
        ),
    )
    monkeypatch.setattr(
        tasks,
        'commit_kv2_inventory',
        lambda *_: SimpleNamespace(
            observed_secret_count=2,
        ),
    )
    failed_scopes = []
    monkeypatch.setattr(
        tasks, 'mark_kv2_inventory_failed', lambda instance_id, mount: failed_scopes.append((instance_id, mount))
    )
    monkeypatch.setattr(
        tasks,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(rollback=lambda: None),
        ),
    )

    result = tasks.sync_vault_inventory_task.run(
        targets=[{'integration_instance_id': 91}],
        requested_by_user_id=3,
    )
    assert result['status'] == 'partial'
    assert result['committed_mounts'] == 1
    assert result['observed_secrets'] == 2
    assert failed_scopes == [(91, 'second')]
    assert contexts[0].status == 'succeeded'
    assert contexts[0].partial is True

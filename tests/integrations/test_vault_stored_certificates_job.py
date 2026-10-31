"""Dedicated Vault stored-cert job stays bounded and credential free."""

from types import SimpleNamespace

import pytest

from app.integrations.secrets_management.secrets_pki import stored_certificate_jobs
from app.platform_operations.jobs.registry import get_job_definition


def test_registered_stored_pki_job_is_separate_and_manual_by_default():
    job = get_job_definition('secrets_pki.pki.stored_certs.sync')
    assert job.queue_name == 'inventory'
    assert job.domain == 'Secrets & PKI'
    assert job.job_type == 'secrets_pki_stored_certificates'
    assert job.operation == 'sync_secrets_pki_stored_certificates'
    assert job.default_enabled is False
    assert job.execute_permission == 'jobs.execute'
    assert job.domain_execute_permission == 'secrets_pki.sync'
    assert job.configure_permission == 'integrations.manage'


def test_stored_cert_job_task_payload_contains_no_mount_or_serial(monkeypatch):
    monkeypatch.setattr(
        stored_certificate_jobs,
        'build_stored_certificate_targets',
        lambda: [{'integration_instance_id': 14}],
    )
    monkeypatch.setattr(
        stored_certificate_jobs,
        'enqueue_canonical_job',
        lambda **kwargs: (kwargs, True),
    )
    dispatched, created = stored_certificate_jobs.enqueue_stored_certificate_sync(
        requested_by_user_id=7,
        trigger_type='manual',
    )
    assert created is True
    assert dispatched['queue_name'] == 'inventory'
    assert dispatched['task_kwargs']['targets'] == [{'integration_instance_id': 14}]
    assert dispatched['dispatch_options'].require_registered_worker
    assert dispatched['max_attempts'] == 1
    serialized = repr(dispatched['task_kwargs']) + repr(dispatched['payload'])
    for forbidden in ('serial_hex', 'pki/', 'private_key', 'pem', 'secret_id', 'client_token'):
        assert forbidden not in serialized


def test_no_approved_pki_target_blocks_enqueue(monkeypatch):
    monkeypatch.setattr(stored_certificate_jobs, 'build_vault_pki_targets', lambda: [])
    with pytest.raises(stored_certificate_jobs.NoEligibleVaultPKITargets):
        stored_certificate_jobs.enqueue_stored_certificate_sync(
            requested_by_user_id=7,
            trigger_type='manual',
        )


def test_task_does_not_treat_partial_mount_success_as_complete(monkeypatch):
    from app.integrations.secrets_management.secrets_pki import tasks

    class Context:
        result = None

        def __init__(self, *_args):
            pass

        def start(self, **_kwargs):
            pass

        def checkpoint(self, **_kwargs):
            pass

        def fail(self, *_args, **_kwargs):
            self.result = 'failed'

        def succeed(self, *, result_summary, result_type, partial):
            self.result = (result_summary, result_type, partial)

        def canceled(self):
            self.result = 'canceled'

    identity = SimpleNamespace(
        integration_type='secrets_pki',
        provider_key='vault',
        enabled=True,
        lifecycle_status='active',
        readiness_status='ready',
    )
    provider = SimpleNamespace(integration_instance=identity, pki_mounts=['a', 'b'], pki_stored_certs_enabled=True)
    monkeypatch.setattr(
        tasks,
        'VaultInstance',
        SimpleNamespace(
            query=SimpleNamespace(
                filter_by=lambda **kwargs: SimpleNamespace(
                    first=lambda: provider,
                )
            )
        ),
    )
    monkeypatch.setattr(tasks, 'JobExecutionContext', Context)
    monkeypatch.setattr(tasks, 'build_client', lambda _: object())
    # The collector is imported locally, so override the source module.
    from app.integrations.secrets_management.secrets_pki.providers.vault import pki_stored_certificates

    monkeypatch.setattr(
        pki_stored_certificates,
        'collect_pki_stored_certificates',
        lambda _client, *, mount: (
            SimpleNamespace(mount=mount)
            if mount == 'a'
            else (_ for _ in ()).throw(ValueError('private-provider-serial'))
        ),
    )
    from app.integrations.secrets_management.secrets_pki import commit_stored_certificates

    monkeypatch.setattr(
        commit_stored_certificates,
        'commit_stored_pki_certificates',
        lambda *_args: SimpleNamespace(observed_count=2),
    )
    failed = []
    monkeypatch.setattr(
        commit_stored_certificates,
        'mark_stored_pki_certificates_failed',
        lambda instance_id, mount: failed.append((instance_id, mount)),
    )
    monkeypatch.setattr(
        tasks,
        'db',
        SimpleNamespace(session=SimpleNamespace(rollback=lambda: None)),
    )
    result = tasks.sync_vault_stored_certificates_task.run(
        targets=[{'integration_instance_id': 14}],
        requested_by_user_id=7,
    )
    assert result['status'] == 'partial'
    assert result['committed_mounts'] == 1
    assert result['observed_stored_certificates'] == 2
    assert result['failed_scopes'] == 1
    assert failed == [(14, 'b')]


def test_job_targets_require_extra_stored_cert_enumeration_approval(monkeypatch):
    monkeypatch.setattr(
        stored_certificate_jobs,
        'build_vault_pki_targets',
        lambda: [{'integration_instance_id': 42}],
    )
    provider = SimpleNamespace(pki_stored_certs_enabled=False)
    monkeypatch.setattr(
        stored_certificate_jobs,
        'VaultInstance',
        SimpleNamespace(
            query=SimpleNamespace(
                filter_by=lambda **kwargs: SimpleNamespace(
                    first=lambda: provider,
                )
            )
        ),
    )
    assert stored_certificate_jobs.build_stored_certificate_targets() == []
    provider.pki_stored_certs_enabled = True
    assert stored_certificate_jobs.build_stored_certificate_targets() == [
        {'integration_instance_id': 42},
    ]

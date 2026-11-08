"""Public PKI jobs must use the canonical inventory worker without credential payloads."""

from types import SimpleNamespace

import pytest

from app.integrations.secrets_management.secrets_pki import pki_sync_jobs
from app.platform_operations.jobs.registry import get_job_definition


def test_registered_pki_job_is_isolated_and_default_disabled():
    job = get_job_definition('secrets_pki.pki.sync')
    assert job.domain == 'Secrets & PKI'
    assert job.queue_name == 'inventory'
    assert job.default_enabled is False
    assert job.configure_permission == 'integrations.manage'
    assert job.execute_permission == 'jobs.execute'
    assert job.domain_execute_permission == 'secrets_pki.sync'
    assert job.job_type == 'secrets_pki_public_pki'


def test_pki_dispatch_passes_only_canonical_instance_ids(monkeypatch):
    monkeypatch.setattr(
        pki_sync_jobs,
        'build_vault_pki_targets',
        lambda: [
            {'integration_instance_id': 42},
        ],
    )
    monkeypatch.setattr(pki_sync_jobs, 'enqueue_canonical_job', lambda **kwargs: (kwargs, True))
    dispatched, created = pki_sync_jobs.enqueue_vault_pki_sync(
        requested_by_user_id=4,
        trigger_type='manual',
    )
    assert created
    assert dispatched['task_kwargs']['targets'] == [{'integration_instance_id': 42}]
    assert dispatched['max_attempts'] == 1
    assert dispatched['dispatch_options'].soft_time_limit_seconds == 1740
    assert dispatched['dispatch_options'].hard_time_limit_seconds == 1800
    assert dispatched['dispatch_options'].require_registered_worker is True
    serialized = repr(dispatched['task_kwargs']) + repr(dispatched['payload'])
    for forbidden in ('pki/', 'private_key', 'subject', 'pem', 'secret_id', 'role_id', 'token'):
        assert forbidden not in serialized


def test_invalid_and_unapproved_pki_mounts_are_not_auto_discovered(monkeypatch):
    def instance(number, *, mounts=('pki',), eligible=True):
        identity = SimpleNamespace(
            id=number,
            integration_type='secrets_pki',
            provider_key='vault',
            enabled=True,
            lifecycle_status='active',
            readiness_status='ready' if eligible else 'validation_required',
        )
        return SimpleNamespace(id=number, integration_instance=identity, pki_mounts=list(mounts))

    class FakeQuery:
        def order_by(self, *_args):
            return self

        def limit(self, *_args):
            return self

        def all(self):
            return [
                instance(1),
                instance(2, mounts=()),
                instance(3, mounts=('../pki',)),
                instance(4, mounts=('pki-stage',), eligible=False),
            ]

    monkeypatch.setattr(
        pki_sync_jobs,
        'VaultInstance',
        SimpleNamespace(id=SimpleNamespace(asc=lambda: None), query=FakeQuery()),
    )
    assert pki_sync_jobs.build_vault_pki_targets() == [{'integration_instance_id': 1}]


def test_empty_target_set_is_not_dispatched(monkeypatch):
    monkeypatch.setattr(pki_sync_jobs, 'build_vault_pki_targets', lambda: [])
    with pytest.raises(pki_sync_jobs.NoEligibleVaultPKITargets):
        pki_sync_jobs.enqueue_vault_pki_sync(requested_by_user_id=4, trigger_type='manual')

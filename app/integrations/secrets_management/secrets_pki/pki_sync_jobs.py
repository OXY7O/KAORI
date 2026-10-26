"""Canonical job admission for bounded public Vault PKI issuer collection."""

from __future__ import annotations

from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    parse_approved_pki_mounts,
)
from app.models.vault import VaultInstance
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job

JOB_KEY = 'secrets_pki.pki.sync'
OPERATION = 'sync_secrets_pki_public_issuers'
MAX_PROVIDER_INSTANCES = 25


class NoEligibleVaultPKITargets(RuntimeError):
    """No explicitly approved Vault PKI source can be observed safely."""


def build_vault_pki_targets() -> list[dict[str, int]]:
    instances = VaultInstance.query.order_by(VaultInstance.id.asc()).limit(MAX_PROVIDER_INSTANCES + 1).all()
    if len(instances) > MAX_PROVIDER_INSTANCES:
        raise NoEligibleVaultPKITargets('Vault PKI provider count exceeds worker capacity.')
    targets: list[dict[str, int]] = []
    for instance in instances:
        identity = instance.integration_instance
        if (
            identity.integration_type != 'secrets_pki'
            or identity.provider_key != 'vault'
            or not identity.enabled
            or identity.lifecycle_status != 'active'
            or identity.readiness_status != 'ready'
        ):
            continue
        try:
            mounts = parse_approved_pki_mounts(','.join(instance.pki_mounts or ()))
        except ValueError:
            # Never turn malformed/empty configuration into broad enumeration.
            continue
        if mounts:
            targets.append({'integration_instance_id': int(identity.id)})
    return targets


def enqueue_vault_pki_sync(*, requested_by_user_id: int | None, trigger_type: str):
    from app.integrations.secrets_management.secrets_pki.tasks import sync_vault_pki_task

    targets = build_vault_pki_targets()
    if not targets:
        raise NoEligibleVaultPKITargets('No Ready Vault instance has an explicitly approved PKI issuer source.')
    return enqueue_canonical_job(
        task=sync_vault_pki_task,
        task_kwargs={'requested_by_user_id': requested_by_user_id, 'targets': targets},
        job_type='secrets_pki_public_pki',
        operation=OPERATION,
        queue_name='inventory',
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='secrets_pki',
        scope_type='secrets_pki_pki_fleet',
        scope_key='all',
        resource_group='secrets-pki-public-pki:global',
        parameters={'scope': 'approved_vault_pki_instances', 'target_count': len(targets)},
        payload={'target_count': len(targets), 'trigger_type': trigger_type},
        max_attempts=1,
        dispatch_options=JobDispatchOptions(
            require_registered_worker=True,
            soft_time_limit_seconds=1740,
            hard_time_limit_seconds=1800,
        ),
    )

"""Vault KV v2 inventory admission through canonical KAORI Jobs & Executions."""

from __future__ import annotations

from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import (
    parse_approved_kv2_mounts,
)
from app.models.vault import VaultInstance
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job

JOB_KEY = 'secrets_pki.inventory.sync'
OPERATION = 'sync_secrets_pki_inventory'
MAX_PROVIDER_INSTANCES = 25


class NoEligibleVaultInventoryTargets(RuntimeError):
    """No explicitly approved and Ready Vault KV v2 collection scopes."""


def build_vault_inventory_targets() -> list[dict[str, int]]:
    targets: list[dict[str, int]] = []
    instances = VaultInstance.query.order_by(VaultInstance.id.asc()).limit(MAX_PROVIDER_INSTANCES + 1).all()
    if len(instances) > MAX_PROVIDER_INSTANCES:
        raise NoEligibleVaultInventoryTargets('Vault inventory provider count exceeds bounded worker capacity.')
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
            mounts = parse_approved_kv2_mounts(','.join(instance.kv2_mounts or ()))
        except ValueError:
            # Invalid provider scope is ineligible; never dispatch a broad fallback.
            continue
        if mounts:
            # Scope references only. Never enqueue paths, mount names, SecretIDs or tokens.
            targets.append({'integration_instance_id': int(identity.id)})
    return targets


def enqueue_vault_inventory_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
):
    from app.integrations.secrets_management.secrets_pki.tasks import sync_vault_inventory_task

    targets = build_vault_inventory_targets()
    if not targets:
        raise NoEligibleVaultInventoryTargets(
            'No enabled, validated Vault instance has explicitly approved KV v2 metadata mounts.'
        )
    return enqueue_canonical_job(
        task=sync_vault_inventory_task,
        task_kwargs={'requested_by_user_id': requested_by_user_id, 'targets': targets},
        job_type='secrets_pki_inventory',
        operation=OPERATION,
        queue_name='inventory',
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='secrets_pki',
        scope_type='secrets_pki_fleet',
        scope_key='all',
        resource_group='secrets-pki-inventory:global',
        parameters={'scope': 'approved_vault_instances', 'target_count': len(targets)},
        payload={'target_count': len(targets), 'trigger_type': trigger_type},
        max_attempts=1,
        dispatch_options=JobDispatchOptions(
            require_registered_worker=True,
            soft_time_limit_seconds=1740,
            hard_time_limit_seconds=1800,
        ),
    )

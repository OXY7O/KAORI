"""Inventory worker: metadata-only Vault reads, committed-state reconciliation."""

from __future__ import annotations

from celery import shared_task

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.commit_inventory import (
    commit_kv2_inventory, mark_kv2_inventory_failed,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.adapter import build_client
from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import (
    collect_kv2_metadata,
    parse_approved_kv2_mounts,
)
from app.models.vault import VaultInstance
from app.platform_operations.jobs.execution import (
    JobCancellationRequested, JobExecutionContext,
)


@shared_task(
    bind=True, name='app.integrations.secrets_management.secrets_pki.tasks.sync_vault_inventory',
    acks_late=True, reject_on_worker_lost=True,
)
def sync_vault_inventory_task(
    self, *, targets: list[dict[str, int]], requested_by_user_id: int | None,
    job_execution_id: int | None = None,
) -> dict[str, int | str]:
    """Run read-only scans; no credentials or sensitive paths in task arguments/results."""
    context = JobExecutionContext(str(self.request.id), job_execution_id)
    count = len(targets)
    succeeded = 0
    failed = 0
    secrets = 0
    if not 1 <= count <= 25:
        context.fail('Vault inventory target scope is invalid.', error_code='invalid_scope')
        return {'status': 'failed', 'synced_instances': 0, 'failed_scopes': count}
    context.start(
        message='Preparing approved Vault metadata scopes.', total=count, percent=1,
        stage='Preparing Inventory', target='Secrets & PKI',
    )
    try:
        for index, target in enumerate(targets, start=1):
            context.checkpoint(
                current=index - 1, total=count, percent=min(5 + 85 * (index - 1) // count, 90),
                stage='Collecting Metadata', target='Vault Instance',
            )
            current_mount: str | None = None
            instance_id = 0
            try:
                instance_id = int(target['integration_instance_id'])
                instance = VaultInstance.query.filter_by(integration_instance_id=instance_id).first()
                if instance is None:
                    raise ValueError('Vault instance no longer exists.')
                identity = instance.integration_instance
                if (
                    identity.integration_type != 'secrets_pki'
                    or identity.provider_key != 'vault'
                    or not identity.enabled
                    or identity.lifecycle_status != 'active'
                    or identity.readiness_status != 'ready'
                ):
                    raise ValueError('Vault inventory scope is no longer eligible.')
                mounts = parse_approved_kv2_mounts(','.join(instance.kv2_mounts or ()))
                if not mounts:
                    raise ValueError('Vault inventory mount scope is not configured.')
                for mount in mounts:
                    current_mount = mount
                    # Do not print/log mount names or provider response objects.
                    context.checkpoint(
                        current=index - 1, total=count, stage='Observing KV v2 Metadata',
                        target='Approved Vault Scope',
                    )
                    # New client per mount; the AppRole token stays only in worker memory.
                    evidence = collect_kv2_metadata(build_client(instance), mount=mount)
                    result = commit_kv2_inventory(instance_id, evidence)
                    secrets += result.observed_secret_count
                    current_mount = None
                succeeded += 1
            except JobCancellationRequested:
                db.session.rollback()
                raise
            except Exception:
                # Provider exceptions may contain URLs, paths or other secrets.
                # Never serialize, log or notify the raw exception.
                db.session.rollback()
                if instance_id and current_mount:
                    mark_kv2_inventory_failed(instance_id, current_mount)
                failed += 1
            context.checkpoint(
                current=index, total=count, percent=min(5 + 90 * index // count, 95),
                stage='Scope Reconciliation', target='Vault Inventory',
            )
        result = {
            'status': 'failed' if failed == count else ('partial' if failed else 'success'),
            'synced_instances': succeeded, 'failed_scopes': failed,
            'observed_secrets': secrets,
        }
        if failed == count:
            context.fail('All approved Vault inventory scopes failed; committed history is retained.',
                         error_code='vault_inventory_failed')
        else:
            context.succeed(result_summary=result, result_type='secrets_pki_inventory',
                            partial=bool(failed))
        return result
    except JobCancellationRequested:
        context.canceled()
        return {'status': 'canceled', 'synced_instances': succeeded, 'failed_scopes': failed}

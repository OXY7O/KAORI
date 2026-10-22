"""Inventory worker: metadata-only Vault reads, committed-state reconciliation."""

from __future__ import annotations

from billiard.exceptions import SoftTimeLimitExceeded
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
    committed_mounts = 0
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
                    committed_mounts += 1
                    secrets += result.observed_secret_count
                    current_mount = None
                succeeded += 1
            except JobCancellationRequested:
                db.session.rollback()
                raise
            except SoftTimeLimitExceeded:
                db.session.rollback()
                if instance_id and current_mount:
                    mark_kv2_inventory_failed(instance_id, current_mount)
                context.fail(
                    'Vault inventory exceeded its bounded worker time; committed evidence retained.',
                    error_code='vault_inventory_timeout',
                )
                return {
                    'status': 'failed', 'synced_instances': succeeded,
                    'failed_scopes': failed + 1, 'committed_mounts': committed_mounts,
                }
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
            'status': 'failed' if failed and not committed_mounts else ('partial' if failed else 'success'),
            'synced_instances': succeeded, 'failed_scopes': failed,
            'observed_secrets': secrets, 'committed_mounts': committed_mounts,
        }
        if failed and not committed_mounts:
            context.fail('All approved Vault inventory scopes failed; committed history is retained.',
                         error_code='vault_inventory_failed')
        else:
            context.succeed(result_summary=result, result_type='secrets_pki_inventory',
                            partial=bool(failed))
        return result
    except JobCancellationRequested:
        context.canceled()
        return {'status': 'canceled', 'synced_instances': succeeded, 'failed_scopes': failed}


@shared_task(
    bind=True, name='app.integrations.secrets_management.secrets_pki.tasks.sync_vault_pki',
    acks_late=True, reject_on_worker_lost=True,
)
def sync_vault_pki_task(
    self, *, targets: list[dict[str, int]], requested_by_user_id: int | None,
    job_execution_id: int | None = None,
) -> dict[str, int | str]:
    """Qualified issuer/CA fingerprint collection; no private or PEM task payloads."""
    from app.integrations.secrets_management.secrets_pki.commit_pki import (
        commit_pki_public_issuers,
        mark_pki_public_issuers_failed,
    )
    from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
        collect_pki_public_issuers,
        parse_approved_pki_mounts,
    )

    context = JobExecutionContext(str(self.request.id), job_execution_id)
    count = len(targets)
    if not 1 <= count <= 25:
        context.fail('Vault PKI target scope is invalid.', error_code='invalid_scope')
        return {'status': 'failed', 'synced_instances': 0, 'failed_scopes': count}
    succeeded = 0
    failed = 0
    committed = 0
    observed_issuers = 0
    context.start(
        message='Preparing approved public Vault PKI scopes.', total=count,
        percent=1, stage='Preparing Public PKI Inventory', target='Secrets & PKI',
    )
    try:
        for index, target in enumerate(targets, start=1):
            context.checkpoint(
                current=index - 1, total=count, percent=min(5 + 85 * (index - 1) // count, 90),
                stage='Collecting Public PKI', target='Vault Instance',
            )
            instance_id = 0
            current_mount: str | None = None
            try:
                instance_id = int(target['integration_instance_id'])
                instance = VaultInstance.query.filter_by(integration_instance_id=instance_id).first()
                if instance is None:
                    raise ValueError('Vault PKI source no longer exists.')
                identity = instance.integration_instance
                if (
                    identity.integration_type != 'secrets_pki'
                    or identity.provider_key != 'vault' or not identity.enabled
                    or identity.lifecycle_status != 'active'
                    or identity.readiness_status != 'ready'
                ):
                    raise ValueError('Vault PKI provider identity is not eligible.')
                mounts = parse_approved_pki_mounts(','.join(instance.pki_mounts or ()))
                if not mounts:
                    raise ValueError('No explicitly approved PKI mount.')
                for mount in mounts:
                    current_mount = mount
                    context.checkpoint(
                        current=index - 1, total=count, stage='Observing Public PKI Issuers',
                        target='Approved Vault PKI Scope',
                    )
                    evidence = collect_pki_public_issuers(build_client(instance), mount=mount)
                    summary = commit_pki_public_issuers(instance_id, evidence)
                    observed_issuers += summary.observed_issuer_count
                    committed += 1
                    current_mount = None
                succeeded += 1
            except JobCancellationRequested:
                db.session.rollback()
                raise
            except SoftTimeLimitExceeded:
                db.session.rollback()
                if instance_id and current_mount:
                    mark_pki_public_issuers_failed(instance_id, current_mount)
                context.fail(
                    'Vault PKI inventory exceeded its bounded worker time; committed evidence retained.',
                    error_code='vault_pki_timeout',
                )
                return {
                    'status': 'failed', 'synced_instances': succeeded,
                    'failed_scopes': failed + 1, 'committed_mounts': committed,
                }
            except Exception:
                # Never expose provider errors/issuer identities/PEM material in job summaries.
                db.session.rollback()
                if instance_id and current_mount:
                    mark_pki_public_issuers_failed(instance_id, current_mount)
                failed += 1
            context.checkpoint(
                current=index, total=count, percent=min(5 + 90 * index // count, 95),
                stage='PKI Evidence Reconciliation', target='Public PKI Inventory',
            )
        status = 'failed' if failed and not committed else ('partial' if failed else 'success')
        result = {
            'status': status, 'synced_instances': succeeded, 'failed_scopes': failed,
            'observed_issuers': observed_issuers, 'committed_mounts': committed,
        }
        if failed and not committed:
            context.fail(
                'All Vault PKI issuer scopes failed; committed history is retained.',
                error_code='vault_pki_collection_failed',
            )
        else:
            context.succeed(
                result_summary=result, result_type='secrets_pki_public_pki',
                partial=bool(failed),
            )
        return result
    except JobCancellationRequested:
        context.canceled()
        return {
            'status': 'canceled', 'synced_instances': succeeded, 'failed_scopes': failed,
        }

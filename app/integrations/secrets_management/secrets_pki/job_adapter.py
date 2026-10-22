"""Canonical registered-job adapter for Vault KV v2 inventory."""

from __future__ import annotations

from app.common.job_execution_presentation import present_job_execution
from app.integrations.secrets_management.secrets_pki.sync_jobs import (
    NoEligibleVaultInventoryTargets, build_vault_inventory_targets,
    enqueue_vault_inventory_sync,
)
from app.models.job import JobExecution, JobPolicy
from app.models.vault import VaultInstance
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.policies.presentation import present_interval


def dispatch_vault_inventory_sync(
    *, requested_by_user_id: int | None, trigger_type: str,
    parameters: dict | None = None,
) -> RegisteredJobDispatchResult:
    try:
        job, created = enqueue_vault_inventory_sync(
            requested_by_user_id=requested_by_user_id, trigger_type=trigger_type,
        )
    except NoEligibleVaultInventoryTargets as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message='Vault metadata inventory execution queued.' if created
        else 'Joined the active Vault inventory execution.',
        job=job, created=created,
    )


def build_vault_inventory_sync_context(policy: JobPolicy) -> dict:
    try:
        targets = build_vault_inventory_targets()
        diagnostic = ''
    except NoEligibleVaultInventoryTargets:
        targets = []
        diagnostic = 'Too many Vault instances for bounded collection.'
    jobs = JobExecution.query.filter_by(
        job_type='secrets_pki_inventory', operation='sync_secrets_pki_inventory',
    )
    recent = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    registered = VaultInstance.query.count()
    eligible = len(targets)
    return {
        'registered_system_count': registered,
        'eligible_system_count': eligible,
        'eligible_target_count': eligible,
        'blocked_system_count': max(registered - eligible, 0),
        'diagnostics': [diagnostic] if diagnostic else [],
        'interval_label': present_interval(policy.interval_minutes),
        'latest_job': present_job_execution(recent[0]) if recent else None,
        'recent_jobs': [present_job_execution(job) for job in recent],
    }

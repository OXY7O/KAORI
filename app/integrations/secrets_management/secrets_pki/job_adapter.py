"""Canonical registered-job adapter for Vault KV v2 inventory."""

from __future__ import annotations

from app.common.job_execution_presentation import present_job_execution
from app.integrations.secrets_management.secrets_pki.sync_jobs import (
    NoEligibleVaultInventoryTargets,
    build_vault_inventory_targets,
    enqueue_vault_inventory_sync,
)
from app.models.job import JobExecution, JobPolicy
from app.models.vault import VaultInstance
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.policies.presentation import present_interval


def dispatch_vault_inventory_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict | None = None,
) -> RegisteredJobDispatchResult:
    try:
        job, created = enqueue_vault_inventory_sync(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
        )
    except NoEligibleVaultInventoryTargets as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message='Vault metadata inventory execution queued.'
        if created
        else 'Joined the active Vault inventory execution.',
        job=job,
        created=created,
    )


def build_vault_inventory_sync_context(policy: JobPolicy) -> dict:
    try:
        targets = build_vault_inventory_targets()
        diagnostic = ''
    except NoEligibleVaultInventoryTargets:
        targets = []
        diagnostic = 'Too many Vault instances for bounded collection.'
    jobs = JobExecution.query.filter_by(
        job_type='secrets_pki_inventory',
        operation='sync_secrets_pki_inventory',
    )
    recent = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    registered = VaultInstance.query.count()
    eligible = len(targets)
    active = (
        jobs.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES), JobExecution.completed_at.is_(None))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    state = {
        'label': 'Execution Active' if active else ('Ready' if eligible else 'Blocked'),
        'tone': 'pending' if active else ('normal' if eligible else 'warning'),
        'icon': 'loader-circle' if active else ('circle-check' if eligible else 'shield-alert'),
        'description': 'Vault metadata reconciliation is active.'
        if active
        else (
            'Approved metadata scopes can be reconciled.'
            if eligible
            else 'Configure approved KV v2 mounts on a Ready Vault integration first.'
        ),
    }
    return {
        'registered_system_count': registered,
        'eligible_system_count': eligible,
        'eligible_target_count': eligible,
        'blocked_system_count': max(registered - eligible, 0),
        'diagnostics': [diagnostic] if diagnostic else [],
        'interval_label': present_interval(policy.interval_minutes),
        'latest_job': present_job_execution(recent[0]) if recent else None,
        'recent_jobs': [present_job_execution(job) for job in recent],
        'active_job': present_job_execution(active) if active else None,
        'execution_state': state,
        'configuration_state': {
            'label': 'Execution Active' if active else ('Enabled' if policy.enabled else 'Manual Only'),
            'tone': 'pending' if active else ('normal' if policy.enabled else 'unknown'),
            'icon': 'loader-circle' if active else ('circle-check' if policy.enabled else 'mouse-pointer-click'),
        },
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled else 'disabled',
            'icon': 'circle-check' if policy.enabled else 'circle-pause',
            'description': 'Vault metadata inventory schedule.',
        },
        'readiness_state': {
            'label': 'Sync Eligible' if eligible else 'Blocked',
            'tone': 'normal' if eligible else 'warning',
            'icon': 'link-2' if eligible else 'shield-alert',
            'description': 'Approved Ready Vault scopes.' if eligible else 'No eligible Vault KV v2 metadata mounts.',
        },
    }

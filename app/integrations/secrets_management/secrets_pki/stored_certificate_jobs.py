"""Canonical Jobs admission and read-only execution context for stored Vault PKI."""

from __future__ import annotations

from app.common.job_execution_presentation import present_job_execution
from app.integrations.secrets_management.secrets_pki.pki_sync_jobs import (
    NoEligibleVaultPKITargets,
    build_vault_pki_targets,
)
from app.models.job import JobExecution, JobPolicy
from app.models.vault import VaultInstance
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES, WORKLOAD_STANDARD
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job
from app.platform_operations.jobs.policies.presentation import present_interval


def build_stored_certificate_targets() -> list[dict[str, int]]:
    """Separate operator opt-in for certificate enumeration from issuer reads."""
    candidates = build_vault_pki_targets()
    return [
        item for item in candidates
        if (provider := VaultInstance.query.filter_by(
            integration_instance_id=item['integration_instance_id'],
        ).first()) is not None and provider.pki_stored_certs_enabled
    ]


JOB_KEY = 'secrets_pki.pki.stored_certs.sync'
OPERATION = 'sync_secrets_pki_stored_certificates'


def enqueue_stored_certificate_sync(*, requested_by_user_id: int | None, trigger_type: str):
    from app.integrations.secrets_management.secrets_pki.tasks import sync_vault_stored_certificates_task

    targets = build_stored_certificate_targets()
    if not targets:
        raise NoEligibleVaultPKITargets('No eligible Vault instance has approved PKI mounts.')
    return enqueue_canonical_job(
        task=sync_vault_stored_certificates_task,
        task_kwargs={'requested_by_user_id': requested_by_user_id, 'targets': targets},
        job_type='secrets_pki_stored_certificates',
        operation=OPERATION,
        queue_name='inventory',
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='secrets_pki',
        scope_type='secrets_pki_pki_fleet',
        scope_key='all',
        resource_group='secrets-pki-stored-certificates:global',
        parameters={'scope': 'approved_stored_pki_sources', 'target_count': len(targets)},
        payload={'target_count': len(targets), 'trigger_type': trigger_type},
        max_attempts=1,
        dispatch_options=JobDispatchOptions(
            require_registered_worker=True,
            soft_time_limit_seconds=1740,
            hard_time_limit_seconds=1800,
        ),
    )


def dispatch_stored_certificate_sync(
    *, requested_by_user_id: int | None, trigger_type: str,
    parameters: dict | None = None,
) -> RegisteredJobDispatchResult:
    try:
        job, created = enqueue_stored_certificate_sync(
            requested_by_user_id=requested_by_user_id, trigger_type=trigger_type,
        )
    except NoEligibleVaultPKITargets as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message='Stored Vault PKI certificate collection queued.' if created
        else 'Joined active stored Vault PKI certificate collection.',
        job=job, created=created,
    )


def build_stored_certificate_sync_context(policy: JobPolicy) -> dict:
    try:
        targets = build_stored_certificate_targets()
        diagnostic = ''
    except NoEligibleVaultPKITargets:
        targets = []
        diagnostic = 'Vault PKI provider scope exceeds bounded worker capacity.'
    jobs = JobExecution.query.filter_by(
        job_type='secrets_pki_stored_certificates', operation=OPERATION,
    )
    recent = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    active = jobs.filter(
        JobExecution.status.in_(ACTIVE_JOB_STATUSES),
        JobExecution.completed_at.is_(None),
    ).order_by(JobExecution.updated_at.desc(), JobExecution.id.desc()).first()
    registered = VaultInstance.query.count()
    eligible = len(targets)
    return {
        'registered_system_count': registered,
        'eligible_system_count': eligible,
        'eligible_target_count': eligible,
        'blocked_system_count': max(registered-eligible, 0),
        'diagnostics': [diagnostic] if diagnostic else [],
        'interval_label': present_interval(policy.interval_minutes),
        'latest_job': present_job_execution(recent[0]) if recent else None,
        'recent_jobs': [present_job_execution(item) for item in recent],
        'active_job': present_job_execution(active) if active else None,
        'execution_state': {
            'label': 'Execution Active' if active else ('Ready' if eligible else 'Blocked'),
            'tone': 'pending' if active else ('normal' if eligible else 'warning'),
            'icon': 'loader-circle' if active else ('circle-check' if eligible else 'shield-alert'),
            'description': 'Source-qualified stored PKI enumeration, bounded to 64 per mount.',
        },
        'configuration_state': {
            'label': 'Execution Active' if active else ('Enabled' if policy.enabled else 'Manual Only'),
            'tone': 'pending' if active else ('normal' if policy.enabled else 'unknown'),
            'icon': 'loader-circle' if active else ('circle-check' if policy.enabled else 'mouse-pointer-click'),
        },
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled else 'disabled',
            'icon': 'circle-check' if policy.enabled else 'circle-pause',
            'description': 'Stored certificate enumeration is optional and manual by default.',
        },
        'readiness_state': {
            'label': 'Sync Eligible' if eligible else 'Blocked',
            'tone': 'normal' if eligible else 'warning',
            'icon': 'link-2' if eligible else 'shield-alert',
            'description': 'Only approved Vault PKI sources; actual stored-cert LIST ACL is separately evaluated.',
        },
    }

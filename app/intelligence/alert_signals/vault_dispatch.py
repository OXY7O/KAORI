"""Manual-only Vault Alert observation dispatch, separate from worker execution.

JobExecution admission and queue/policy safety are unchanged; authoritative
observation and revalidation stay in vault_jobs and the registered Celery task.
"""

from __future__ import annotations

from app.intelligence.alert_signals.vault_jobs import (
    JOB_TYPE,
    OPERATION,
    NoEligibleVaultAlertSources,
    build_vault_alert_observation_targets,
)
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job


def dispatch_vault_alert_observations(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict | None = None,
) -> RegisteredJobDispatchResult:
    """Manual operator UAT only; no policy/Beat scheduling is admitted."""
    if trigger_type != 'manual':
        return RegisteredJobDispatchResult(
            status='blocked',
            message='Vault alert observation is manual-only.',
        )
    try:
        targets = build_vault_alert_observation_targets()
    except NoEligibleVaultAlertSources as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    if not targets:
        return RegisteredJobDispatchResult(
            status='blocked',
            message='No qualified Vault Alert Source is eligible.',
        )
    from app.intelligence.alert_signals.tasks import observe_vault_alert_source

    job, created = enqueue_canonical_job(
        task=observe_vault_alert_source,
        task_kwargs={'binding_ids': targets},
        job_type=JOB_TYPE,
        operation=OPERATION,
        queue_name='inventory',
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='secrets_pki',
        scope_type='secrets_pki_alert_fleet',
        scope_key='all',
        resource_group='secrets-pki-vault-alerts:global',
        parameters={'scope': 'qualified_vault_alert_sources', 'target_count': len(targets)},
        payload={'target_count': len(targets), 'trigger_type': 'manual'},
        max_attempts=1,
        dispatch_options=JobDispatchOptions(
            require_registered_worker=True,
            soft_time_limit_seconds=240,
            hard_time_limit_seconds=300,
        ),
    )
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message='Vault alert evidence collection queued.' if created else 'Joined the active observation.',
        job=job,
        created=created,
    )

from __future__ import annotations

from typing import Any

from flask import current_app, url_for

from app.integrations.delivery.notification_channels.contracts import NotificationEvent, NotificationMessage
from app.integrations.delivery.notification_channels.service import dispatch_matching_notification_event
from app.models.job import JobExecution

FAILED_JOB_EVENT = 'jobs.execution_failed'


def build_failed_job_event(job: JobExecution) -> NotificationEvent:
    """Project *committed* JobExecution failure without raw error or job parameters."""
    if job.status != 'failed':
        raise ValueError('Only committed failed JobExecutions can produce this outbound event.')

    base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '').strip().rstrip('/')
    path = url_for('jobs.executions')
    job_name = str(job.job_type or 'Background Job')[:100]
    job_identity = str(job.public_id)
    message = NotificationMessage(
        title=f'Job Failed · {job_name}',
        body='\n'.join(
            (
                'A canonical KAORI job has failed. Review the committed job evidence in Operations Center.',
                f'Job: {job_identity}',
                f'Type: {job_name}',
                f'Status: {job.status}',
            )
        ),
        severity='warning',
        action_url=f'{base_url}{path}' if base_url else path,
        action_label='Review Job Execution',
    )
    return NotificationEvent(
        event_type=FAILED_JOB_EVENT,
        domain='platform_operations',
        asset_type='job_execution',
        asset_key=job_identity,
        severity='warning',
        event_key=f'{FAILED_JOB_EVENT}:{job_identity}',
        message=message,
        payload={
            'job_public_id': job_identity,
            'job_type': job_name,
            'status': job.status,
        },
    )


def dispatch_failed_job_event(job: JobExecution) -> dict[str, Any]:
    """Deliver via the existing per-channel durable journal; never synthesize audit."""
    return dispatch_matching_notification_event(event=build_failed_job_event(job))

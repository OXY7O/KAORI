from __future__ import annotations

from typing import Any

from app.extensions.db import db
from app.jobs.definitions.base import RegisteredJobDispatchResult
from app.jobs.dispatcher import enqueue_canonical_job
from app.models.report import Report
from app.reports.jobs.contract import build_report_job_parameters
from app.reports.jobs.tasks import generate_report_job

JOB_TYPE = 'report_generation'
OPERATION = 'generate_report_artifact'
QUEUE_NAME = 'reports'


def enqueue_report_generation(
    report: Report,
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    schedule_id: int | None = None,
    schedule_run_id: int | None = None,
) -> RegisteredJobDispatchResult:
    parameters = build_report_job_parameters(
        report,
        trigger_type=trigger_type,
        schedule_id=schedule_id,
        schedule_run_id=schedule_run_id,
    )
    payload = parameters.to_payload()
    resource_group = f'report:{report.id}'
    job, created = enqueue_canonical_job(
        task=generate_report_job,
        task_kwargs={'report_id': int(report.id)},
        job_type=JOB_TYPE,
        operation=OPERATION,
        queue_name=QUEUE_NAME,
        workload_class='heavy' if parameters.report_family == 'analytics' else 'standard',
        requested_by_user_id=requested_by_user_id,
        provider_type='kubernetes',
        scope_type='cluster',
        scope_key=parameters.selected_cluster_id,
        resource_group=resource_group,
        parameters=payload,
        payload=payload,
        max_attempts=3,
        soft_time_limit_seconds=1800,
        hard_time_limit_seconds=1860,
    )
    report.job_execution_id = job.id
    report.status = 'queued' if report.status == 'requested' else report.status
    db.session.commit()
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message='Report generation was queued.' if created else 'The request joined the active report generation job.',
        job=job,
        created=created,
    )

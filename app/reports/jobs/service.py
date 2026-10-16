from __future__ import annotations

from app.extensions.db import db
from app.models.report import Report
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job
from app.reports.jobs.contract import build_report_job_parameters
from app.reports.jobs.queue import get_reports_queue_name
from app.reports.jobs.tasks import generate_report_job

JOB_TYPE = 'report_generation'
OPERATION = 'generate_report_artifact'


def get_report_job_integration_dimensions(scope_asset_type: str, scope_asset_id: str) -> tuple[str | None, int | None]:
    """Keep JobExecution dimensions aligned with canonical asset ownership."""
    integration_types = {
        'kubernetes_cluster': 'kubernetes',
        'object_storage_system': 'object_storage',
        'registry_integration': 'registry',
    }
    integration_type = integration_types.get(scope_asset_type)
    if scope_asset_type == 'registry_integration':
        # The registry integration identity is an IntegrationInstance primary key.
        return integration_type, int(scope_asset_id)
    return integration_type, None


class ReportJobEnqueueError(RuntimeError):
    """Raised when KAORI cannot register or dispatch a report job."""


def enqueue_report_generation(
    report: Report,
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    schedule_id: int | None = None,
    schedule_run_id: int | None = None,
) -> RegisteredJobDispatchResult:
    try:
        parameters = build_report_job_parameters(
            report,
            trigger_type=trigger_type,
            schedule_id=schedule_id,
            schedule_run_id=schedule_run_id,
        )
        payload = parameters.to_payload()
        resource_group = f'report:{report.id}'
        integration_type, integration_instance_id = get_report_job_integration_dimensions(
            parameters.scope_asset_type, parameters.scope_asset_id
        )
        job, created = enqueue_canonical_job(
            task=generate_report_job,
            task_kwargs={
                'report_id': int(report.id),
                'schedule_run_id': schedule_run_id,
            },
            job_type=JOB_TYPE,
            operation=OPERATION,
            queue_name=get_reports_queue_name(),
            workload_class='heavy' if parameters.report_family == 'analytics' else 'standard',
            requested_by_user_id=requested_by_user_id,
            integration_type=integration_type,
            integration_instance_id=integration_instance_id,
            scope_type=parameters.scope_asset_type,
            scope_key=parameters.scope_asset_id,
            resource_group=resource_group,
            parameters=payload,
            payload=payload,
            max_attempts=3,
            dispatch_options=JobDispatchOptions(
                soft_time_limit_seconds=1800,
                hard_time_limit_seconds=1860,
                require_registered_worker=False,
            ),
        )
        report.job_execution_id = job.id
        if report.status in {'requested', 'failed'}:
            report.status = 'queued'
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        raise ReportJobEnqueueError('KAORI could not enqueue the report generation job.') from exc

    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message='Report generation was queued.' if created else 'The request joined the active report generation job.',
        job=job,
        created=created,
    )

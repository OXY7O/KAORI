from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.jobs.execution import JobExecutionContext
from app.jobs.service import subscriber_user_ids
from app.models.job import JobExecution
from app.models.report import Report, ReportSchedule, ReportScheduleRun
from app.notifications.feedback import OperationalDeliveryPolicy
from app.notifications.service import record_operational_activity
from app.reports.export.service import generate_report_artifact
from app.reports.notifications import deliver_generated_report


def _notify(job: JobExecution, report: Report, *, success: bool, message: str) -> None:
    users = set(subscriber_user_ids(job))
    if report.generated_by_id:
        users.add(report.generated_by_id)

    title = 'Report Ready' if success else 'Report Generation Failed'
    public_message = (
        f'{report.name} is ready for download.'
        if success
        else f'KAORI could not complete {report.name}. Review generation evidence before retrying.'
    )

    for user_id in users:
        record_operational_activity(
            user_id=user_id,
            event_type='report_generation_completed' if success else 'report_generation_failed',
            status='success' if success else 'error',
            title=title,
            message=public_message,
            detail=f'{report.output_format.upper()} · {message}',
            action_url=f'/reports/generated/{report.id}',
            action_label='Open report',
            action_icon='file-text',
            metadata={
                'feedback_delivery': 'activity_center',
                'job_execution_id': job.id,
                'job_public_id': job.public_id,
                'report_id': report.id,
                'report_name': report.name,
                'report_type': report.report_type,
                'output_format': report.output_format,
                'status': report.status,
            },
            delivery_policy=OperationalDeliveryPolicy.PERSISTENT,
        )


def _finalize_schedule(
    report: Report,
    *,
    schedule_run_id: int | None,
    success: bool,
    message: str,
) -> None:
    if schedule_run_id is None:
        return
    run = db.session.get(ReportScheduleRun, schedule_run_id)
    if run is None or run.report_id != report.id:
        return
    run.status = 'success' if success else 'failed'
    run.finished_at = datetime.now(UTC)
    run.error_message = None if success else message
    schedule = db.session.get(ReportSchedule, run.schedule_id) if run.schedule_id else None
    if schedule is not None:
        schedule.last_status = run.status
        schedule.last_run_at = run.finished_at
        schedule.last_report_id = report.id
        if success:
            run.delivery_result = deliver_generated_report(report, schedule.notification_channel_ids_as_list())
    db.session.commit()


_PUBLIC_WORKER_FAILURE_MESSAGE = (
    'KAORI could not complete report generation or scheduled delivery. Review report scope, '
    'source readiness, storage readiness, delivery configuration, and worker logs before retrying.'
)


@shared_task(
    bind=True,
    name='app.reports.jobs.tasks.generate_report_job',
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(),
)
def generate_report_job(
    self,
    *,
    report_id: int,
    schedule_run_id: int | None = None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    lifecycle = JobExecutionContext(str(self.request.id), job_execution_id)
    lifecycle.start(
        message='Validating report scope and data boundary.',
        total=4,
        percent=5,
        stage='Validating Report Scope',
        target=f'Report {report_id}',
    )
    report = db.session.get(Report, report_id)
    if report is None:
        exc = LookupError(f'Report {report_id} was not found.')
        lifecycle.fail(exc, error_code='report_not_found')
        raise exc

    public_failure_message = _PUBLIC_WORKER_FAILURE_MESSAGE

    try:
        lifecycle.checkpoint(
            current=1,
            total=4,
            percent=20,
            stage='Resolving Evidence Boundary',
            target=f'Report {report_id}',
            message='Resolving selected-cluster evidence boundary.',
        )
        lifecycle.checkpoint(
            current=2,
            total=4,
            percent=55,
            stage='Rendering Report Artifact',
            target=f'Report {report_id}',
            message='Rendering the governed report artifact.',
        )
        success, message = generate_report_artifact(report_id)
        report = db.session.get(Report, report_id) or report
        if not success:
            public_failure_message = message
            raise RuntimeError(message)
        lifecycle.checkpoint(
            current=3,
            total=4,
            percent=90,
            stage='Committing Report Artifact',
            target=f'Report {report_id}',
            message='Committing artifact metadata and delivery state.',
        )
        _finalize_schedule(
            report,
            schedule_run_id=schedule_run_id,
            success=True,
            message=message,
        )
        lifecycle.succeed(
            result_type='report_artifact',
            result_reference=report.file_path,
            result_summary={
                'report_id': report.id,
                'report_type': report.report_type,
                'output_format': report.output_format,
                'file_path': report.file_path,
                'file_size_bytes': report.file_size_bytes,
                'selected_cluster_id': report.cluster_id,
                'period': report.period,
            },
        )
        job = db.session.get(JobExecution, job_execution_id) if job_execution_id else None
        if job is not None:
            _notify(job, report, success=True, message=message)
        return {'status': 'ready', 'report_id': report.id, 'file_path': report.file_path}
    except Exception as exc:
        db.session.rollback()
        report = db.session.get(Report, report_id) or report
        _finalize_schedule(
            report,
            schedule_run_id=schedule_run_id,
            success=False,
            message=public_failure_message,
        )
        lifecycle.fail(exc, error_code='report_generation_failed')
        job = db.session.get(JobExecution, job_execution_id) if job_execution_id else None
        if job is not None:
            _notify(job, report, success=False, message=public_failure_message)
        raise

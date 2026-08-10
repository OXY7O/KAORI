from __future__ import annotations

from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.jobs.execution import JobExecutionContext
from app.models.report import ReportSchedule
from app.reports.schedules.service import execute_schedule, run_due_schedules


@shared_task(
    bind=True,
    name='app.reports.schedules.tasks.run_report_schedule_job',
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_report_schedule_job(
    self,
    *,
    schedule_id: int | None = None,
    limit: int = 20,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    lifecycle = JobExecutionContext(task_id, job_execution_id)
    lifecycle.start(
        message='Preparing scheduled report generation.',
        total=1 if schedule_id is not None else max(limit, 1),
    )
    try:
        if schedule_id is not None:
            schedule = db.session.get(ReportSchedule, schedule_id)
            if schedule is None:
                raise LookupError('Report schedule not found.')
            lifecycle.checkpoint(current=0, total=1, message=f'Generating {schedule.name}.')
            success, message, report_id = execute_schedule(schedule, trigger_source='manual')
            result = {
                'mode': 'single_schedule',
                'schedule_id': schedule_id,
                'report_id': report_id,
                'success': success,
                'message': message,
            }
            if not success:
                raise RuntimeError(message)
            lifecycle.checkpoint(current=1, total=1, message='Scheduled report generated.')
        else:
            result = run_due_schedules(limit=limit, dry_run=False)
            failures = [item for item in result['results'] if item.get('status') == 'failed']
            lifecycle.checkpoint(
                current=result['due_count'],
                total=max(result['due_count'], 1),
                message=f'Processed {result["due_count"]} due report schedule(s).',
            )
            if failures:
                result['partial'] = True

        lifecycle.succeed(
            result_summary=result,
            result_type='report_schedule_dispatch',
            partial=bool(result.get('partial')),
        )
        return result
    except Exception as exc:
        db.session.rollback()
        lifecycle.fail(exc, error_code='report_schedule_generation_failed')
        raise

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.common.celery_queue_health import get_queue_readiness
from app.common.job_execution_presentation import present_job_execution
from app.extensions.db import db
from app.jobs.constants import ACTIVE_JOB_STATUSES
from app.jobs.definitions.base import RegisteredJobDispatchResult
from app.jobs.dispatcher import enqueue_canonical_job
from app.jobs.policies.presentation import present_interval
from app.models.job import JobExecution, JobPolicy
from app.models.report import ReportSchedule
from app.reports.delivery import get_delivery_channel_catalog
from app.reports.jobs.queue import get_reports_queue_name
from app.reports.schedules.tasks import run_report_schedule_job

JOB_TYPE = 'report_schedule'
OPERATION = 'dispatch_due_reports'


def dispatch_report_schedule_job(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    parameters = dict(parameters or {})
    schedule_id = parameters.get('schedule_id')
    limit = max(int(parameters.get('limit') or 20), 1)
    resource_group = f'report-schedule:{schedule_id}' if schedule_id else 'report-schedule:due'
    job, created = enqueue_canonical_job(
        task=run_report_schedule_job,
        task_kwargs={'schedule_id': int(schedule_id) if schedule_id is not None else None, 'limit': limit},
        job_type=JOB_TYPE,
        operation=OPERATION,
        queue_name=get_reports_queue_name(),
        workload_class='standard',
        requested_by_user_id=requested_by_user_id,
        resource_group=resource_group,
        scope_type='report_schedule',
        scope_key=str(schedule_id or 'due'),
        parameters={'schedule_id': schedule_id, 'limit': limit},
        payload={'trigger_type': trigger_type, 'schedule_id': schedule_id, 'limit': limit},
        max_attempts=2,
        soft_time_limit_seconds=1800,
        hard_time_limit_seconds=1860,
    )
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message='Report schedule generation was queued.' if created else 'The request joined an active report schedule job.',
        job=job,
        created=created,
    )


def run_schedule_now(
    schedule_id: int,
    *,
    requested_by_user_id: int | None = None,
) -> tuple[bool, str, int | None]:
    schedule = db.session.get(ReportSchedule, schedule_id)
    if schedule is None:
        return False, 'Schedule not found.', None

    result = dispatch_report_schedule_job(
        requested_by_user_id=requested_by_user_id,
        trigger_type='manual',
        parameters={'schedule_id': schedule_id, 'limit': 1},
    )
    if not result.accepted:
        return False, result.message, None
    return True, result.message, None


def build_report_schedule_context(policy: JobPolicy) -> dict[str, Any]:
    query = JobExecution.query.filter_by(job_type=JOB_TYPE, operation=OPERATION)
    active = (
        query.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES), JobExecution.completed_at.is_(None))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent = query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    latest = recent[0] if recent else None
    active_schedules = ReportSchedule.query.filter_by(is_enabled=True).count()
    due_schedules = ReportSchedule.query.filter(
        ReportSchedule.is_enabled.is_(True),
        ReportSchedule.next_run_at.is_not(None),
        ReportSchedule.next_run_at <= datetime.now(UTC),
    ).count()
    worker_state = get_queue_readiness(get_reports_queue_name())
    execution_state = (
        {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
            'description': 'A report schedule job is running.',
        }
        if active
        else {
            'label': worker_state['label'],
            'tone': worker_state['tone'],
            'icon': worker_state['icon'],
            'description': worker_state['description'],
        }
    )
    return {
        'interval_label': present_interval(policy.interval_minutes),
        'active_schedule_count': active_schedules,
        'tracked_schedule_count': due_schedules,
        'delivery_channels': get_delivery_channel_catalog(),
        'active_job': present_job_execution(active) if active else None,
        'latest_job': present_job_execution(latest) if latest else None,
        'recent_jobs': [present_job_execution(job) for job in recent],
        'execution_state': execution_state,
        'worker_state': worker_state,
        'scheduler_state': {'label': 'Enabled' if policy.enabled else 'Disabled', 'tone': 'normal' if policy.enabled else 'disabled', 'icon': 'circle-check' if policy.enabled else 'circle-pause', 'description': 'Due report schedules are checked automatically.' if policy.enabled else 'Automatic report schedule dispatch is disabled.'},
        'readiness_state': {'label': 'Ready' if active_schedules else 'Waiting For Schedule', 'tone': 'normal' if active_schedules else 'warning', 'icon': 'calendar-check' if active_schedules else 'calendar-x', 'description': f'{active_schedules} enabled report schedule(s) are available.' if active_schedules else 'Create and enable a report schedule before automatic dispatch.'},
        'configuration_state': {'label': 'Configured' if policy.enabled else 'Disabled', 'tone': 'normal' if policy.enabled else 'disabled', 'icon': 'settings-2'},
    }

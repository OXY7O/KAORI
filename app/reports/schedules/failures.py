from __future__ import annotations

from datetime import UTC, datetime

from app.extensions.db import db
from app.models.report import Report, ReportSchedule, ReportScheduleRun

_QUEUE_FAILURE_MESSAGE = (
    'KAORI could not queue the report job. Review the Reports worker, broker, '
    'and queue configuration.'
)
_REPORT_QUEUE_FAILURE_MESSAGE = (
    'KAORI could not queue this scheduled report. Review the Reports worker, '
    'broker, and queue configuration before retrying.'
)


def mark_schedule_dispatch_failed(
    *,
    schedule_id: int,
    schedule_run_id: int,
    report_id: int,
) -> int | None:
    failed_at = datetime.now(UTC)
    run = db.session.get(ReportScheduleRun, schedule_run_id)
    if run is not None:
        run.status = 'failed'
        run.finished_at = failed_at
        run.error_message = _QUEUE_FAILURE_MESSAGE

    report = db.session.get(Report, report_id)
    if report is not None:
        report.status = 'failed'
        report.error_message = _REPORT_QUEUE_FAILURE_MESSAGE

    schedule = db.session.get(ReportSchedule, schedule_id)
    if schedule is not None:
        schedule.last_status = 'failed'
        schedule.last_run_at = failed_at

    db.session.commit()
    return report.id if report is not None else None

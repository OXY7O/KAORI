from __future__ import annotations

from app.extensions.db import db
from app.models.report import Report


def get_report(report_id: int) -> Report | None:
    return db.session.get(Report, report_id)


def mark_report_queue_failure(report_id: int, *, message: str, preserve_ready: bool = False) -> Report | None:
    """Rollback the failed enqueue transaction, then persist durable report failure evidence."""

    db.session.rollback()
    report = db.session.get(Report, report_id)
    if report is None:
        return None
    if preserve_ready and report.status == 'ready':
        return report
    report.status = 'failed'
    report.error_message = message
    db.session.commit()
    return report

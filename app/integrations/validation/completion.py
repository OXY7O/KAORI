from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.platform_operations.jobs.service import mark_job_failed, mark_job_succeeded

logger = logging.getLogger(__name__)


def final_payload(
    *,
    base: dict[str, Any],
    status: str,
    title: str,
    message: str,
    detail: str,
    feedback: dict[str, Any] | None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    finished_at = datetime.now(UTC).isoformat()
    started = datetime.fromisoformat(str(base['started_at']))
    finished = datetime.fromisoformat(finished_at)
    payload = {
        **base,
        'status': status,
        'title': title,
        'message': message,
        'detail': detail,
        'feedback': feedback,
        'result': result or {},
        'finished_at': finished_at,
        'duration_seconds': max(int((finished - started).total_seconds()), 0),
    }
    task_id = str(base.get('task_id') or '')
    if not task_id:
        return payload
    try:
        if status == 'error':
            mark_job_failed(task_id, error=detail, error_code='operation_failed')
        else:
            mark_job_succeeded(
                task_id,
                result_summary=result or {},
                result_type=str(base.get('operation') or 'job_result'),
                partial=status == 'warning',
            )
    except Exception:
        db.session.rollback()
        logger.exception('Could not finalize canonical job record for task %s.', task_id)
    return payload

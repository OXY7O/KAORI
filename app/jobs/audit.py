from __future__ import annotations

from typing import Any

from app.extensions.db import db
from app.jobs.serialization import to_json_compatible
from app.models.audit import AuditEvent
from app.models.job import JobExecution


def is_automatic_execution(job: JobExecution) -> bool:
    payload = job.payload_json or {}
    return job.requested_by_user_id is None and str(payload.get('trigger_type') or '') == 'scheduled'


def record_automatic_job_event(
    job: JobExecution,
    *,
    action: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    """Write an automatic job event to Activity Audit without creating notifications."""
    if not is_automatic_execution(job):
        return
    event = AuditEvent()
    event.actor_user_id = None
    event.target_type = 'job_execution'
    event.target_id = job.public_id
    event.action = action
    event.summary = summary[:255]
    event.metadata_json = to_json_compatible(
        {
            'job_execution_id': job.id,
            'job_public_id': job.public_id,
            'job_type': job.job_type,
            'operation': job.operation,
            'queue_name': job.queue_name,
            'status': job.status,
            **(metadata or {}),
        }
    )
    db.session.add(event)
    if commit:
        db.session.commit()

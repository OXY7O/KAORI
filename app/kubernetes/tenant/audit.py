from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.models.audit import AuditEvent
from app.models.job import JobExecution

logger = logging.getLogger(__name__)


def record_tenant_sync_dispatch_audit(
    *,
    actor_user_id: int,
    action_status: str,
    summary: str,
    job: JobExecution | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'job_execution' if job is not None else 'kubernetes_tenant_inventory'
    event.target_id = job.public_id if job is not None else 'all_clusters'
    event.action = f'kubernetes_tenant_inventory_sync_dispatch_{action_status}'
    event.summary = summary[:255]
    event.metadata_json = {
        'job_execution_id': job.id if job is not None else None,
        'job_public_id': job.public_id if job is not None else None,
        'dispatch_status': action_status,
        **(metadata or {}),
    }
    try:
        db.session.add(event)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Could not persist Tenant sync dispatch audit event.')


def record_tenant_sync_terminal_audit(
    *,
    job: JobExecution | None,
    fallback_user_id: int | None,
    terminal_status: str,
    result: dict[str, Any],
) -> bool:
    if job is None:
        return False

    action = f'kubernetes_tenant_inventory_sync_{terminal_status}'
    existing = AuditEvent.query.filter_by(
        target_type='job_execution',
        target_id=job.public_id,
        action=action,
    ).first()
    if existing is not None:
        return True

    event = AuditEvent()
    event.actor_user_id = job.requested_by_user_id or fallback_user_id
    event.target_type = 'job_execution'
    event.target_id = job.public_id
    event.action = action
    event.summary = {
        'succeeded': 'Tenant inventory synchronization completed successfully.',
        'partially_succeeded': 'Tenant inventory synchronization completed with snapshot exceptions.',
        'failed': 'Tenant inventory synchronization failed.',
        'canceled': 'Tenant inventory synchronization was canceled.',
    }.get(terminal_status, f'Tenant inventory synchronization finished with status {terminal_status}.')[:255]
    event.metadata_json = {
        'job_execution_id': job.id,
        'job_public_id': job.public_id,
        'job_type': job.job_type,
        'operation': job.operation,
        'status': terminal_status,
        'result_summary': result,
    }
    try:
        db.session.add(event)
        db.session.commit()
        return True
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Could not persist terminal Tenant sync audit event for job %s.', job.public_id)
        return False

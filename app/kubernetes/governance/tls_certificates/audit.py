from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.models.audit import AuditEvent

logger = logging.getLogger(__name__)


def record_tls_sync_dispatch_audit(
    *,
    actor_user_id: int,
    action_status: str,
    summary: str,
    cluster_id: str | None,
    job=None,
    metadata: dict[str, object] | None = None,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'job_execution' if job is not None else 'tls_certificate_inventory'
    event.target_id = job.public_id if job is not None else (cluster_id or 'all_clusters')
    event.action = f'governance_tls_secret_sync_dispatch_{action_status}'
    event.summary = summary[:255]
    event.metadata_json = {
        'cluster_id': cluster_id,
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
        logger.exception('Could not persist TLS sync dispatch audit event.')

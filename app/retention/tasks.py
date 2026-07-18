from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from flask import current_app

from app.notifications.service import (
    create_notification,
)
from app.extensions import db
from app.models.user import User
from app.retention.domains import get_archive_domain
from app.retention.service import purge_expired_archives, run_retention_archive

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="app.retention.tasks.run_domain_retention",
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_domain_retention_task(
    self,
    *,
    domain_name: str,
    cleanup: bool,
    trigger_type: str = "manual",
    requested_by_user_id: int | None = None,
) -> dict[str, Any]:
    try:
        result = run_retention_archive(
            domain_name=domain_name,
            trigger_type=trigger_type,
            cleanup=cleanup,
            triggered_by_user_id=requested_by_user_id,
            celery_task_id=self.request.id,
        )
        _notify_requester(
            user_id=requested_by_user_id,
            result=result,
            cleanup=cleanup,
        )
        return result
    except Exception as exc:
        db.session.rollback()
        logger.exception("Retention task failed for %s.", domain_name)
        _notify_failure(
            user_id=requested_by_user_id,
            domain_name=domain_name,
            cleanup=cleanup,
            trigger_type=trigger_type,
            error=exc,
        )
        raise


@shared_task(
    bind=True,
    name="app.retention.tasks.run_scheduled_retention",
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_scheduled_retention_task(self) -> dict[str, Any]:
    configured_domains = current_app.config.get(
        "ARCHIVE_SCHEDULED_DOMAINS",
        ("operational_activity",),
    )
    if isinstance(configured_domains, str):
        configured_domains = tuple(
            item.strip().lower().replace("-", "_")
            for item in configured_domains.split(",")
            if item.strip()
        )

    results: dict[str, Any] = {}
    for domain_name in configured_domains:
        try:
            domain = get_archive_domain(domain_name)
            policy = domain.build_policy()
            if not policy.enabled:
                results[domain_name] = {"status": "disabled"}
                continue

            retention_result = run_retention_archive(
                domain_name=domain_name,
                trigger_type="scheduled",
                cleanup=True,
                triggered_by_user_id=None,
                celery_task_id=self.request.id,
            )
            purge_result = purge_expired_archives(
                domain_name=domain_name,
                retention_days=policy.archive_retention_days,
                dry_run=False,
            )
            results[domain_name] = {
                "retention": retention_result,
                "archive_purge": purge_result,
            }
        except Exception as exc:
            db.session.rollback()
            logger.exception("Scheduled retention failed for %s.", domain_name)
            _notify_failure(
                user_id=None,
                domain_name=domain_name,
                cleanup=True,
                trigger_type="scheduled",
                error=exc,
            )
            results[domain_name] = {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

    return {"domains": results}


def _notify_requester(
    *,
    user_id: int | None,
    result: dict[str, Any],
    cleanup: bool,
) -> None:
    if user_id is None:
        return

    if result.get("status") == "no_data":
        title = "Activity retention found no eligible records"
        message = "No activity records were old enough to archive."
        status = "info"
    else:
        record_count = int(result.get("record_count") or 0)
        deleted_count = int(result.get("cleanup_deleted_count") or 0)
        title = (
            "Activity archive and cleanup completed"
            if cleanup
            else "Activity archive completed"
        )
        message = (
            f"{record_count} activity records were archived and {deleted_count} were removed from hot storage."
            if cleanup
            else f"{record_count} activity records were archived without database cleanup."
        )
        status = "warning" if result.get("status") == "cleanup_partial" else "success"

    _safe_create_notification(
        user_id=user_id,
        status=status,
        title=title,
        message=message,
        detail="Review the Retention & Archive section for archive status, checksum, and download actions.",
        metadata={
            "archive_id": result.get("archive_id"),
            "record_count": result.get("record_count", 0),
            "cleanup_deleted_count": result.get("cleanup_deleted_count", 0),
            "storage_backend": result.get("storage_backend"),
        },
    )


def _notify_failure(
    *,
    user_id: int | None,
    domain_name: str,
    cleanup: bool,
    trigger_type: str,
    error: Exception,
) -> None:
    activity_owner_user_id = _resolve_activity_owner_user_id(user_id)
    if activity_owner_user_id is None:
        return

    actor_metadata: dict[str, Any] = {}
    if trigger_type == "scheduled" and user_id is None:
        actor_metadata = {
            "actor_display_name": "System scheduler",
            "actor_role": "Background worker",
            "actor_email": "Automatic schedule",
            "auth_source": "system",
        }

    _safe_create_notification(
        user_id=activity_owner_user_id,
        status="error",
        title="Activity retention failed",
        message="The archive-first retention job stopped before it could complete safely.",
        detail="Database cleanup remains blocked. Review the Activity Audit Log for the complete technical failure detail before retrying.",
        metadata={
            "domain": domain_name,
            "cleanup_requested": cleanup,
            "trigger_type": trigger_type,
            "error_type": type(error).__name__,
            "reason": _retention_error_summary(error),
            "error_message": f"{type(error).__name__}: {error}",
            **actor_metadata,
        },
    )


def _safe_create_notification(
    *,
    user_id: int,
    status: str,
    title: str,
    message: str,
    detail: str,
    metadata: dict[str, Any],
) -> None:
    try:
        create_notification(
            user_id=user_id,
            event_type="operational_activity_retention",
            status=status,
            title=title,
            message=message,
            detail=detail,
            action_url="/notifications/activity#activity-retention",
            metadata=metadata,
        )
    except Exception:
        db.session.rollback()
        logger.exception("Could not create the retention completion notification.")


def _resolve_activity_owner_user_id(preferred_user_id: int | None) -> int | None:
    if preferred_user_id is not None:
        preferred_user = db.session.get(User, preferred_user_id)
        if (
            preferred_user is not None
            and preferred_user.deleted_at is None
            and preferred_user.is_active
        ):
            return preferred_user.id

    active_users = (
        User.query.filter(User.deleted_at.is_(None), User.account_is_active.is_(True))
        .order_by(User.is_super_admin.desc(), User.created_at.asc(), User.id.asc())
        .all()
    )
    for user in active_users:
        if user.is_admin_level:
            return user.id
    return active_users[0].id if active_users else None


def _retention_error_summary(error: Exception) -> str:
    normalized = str(error).strip()
    lowered = normalized.lower()
    if (
        "endpointconnectionerror" in lowered
        or "could not connect to the endpoint" in lowered
        or "connection refused" in lowered
        or "connection timed out" in lowered
        or "gaierror" in lowered
        or "name or service not known" in lowered
    ):
        return "Archive storage could not be reached."
    if "checksum" in lowered:
        return "Archive verification failed."
    if "access denied" in lowered or "forbidden" in lowered or "permission" in lowered:
        return "Archive storage access was denied."
    if "size verification failed" in lowered or "size mismatch" in lowered:
        return "Archive size verification failed."
    return "Archive lifecycle failed and requires operator review."

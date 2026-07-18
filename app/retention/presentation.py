from __future__ import annotations

import os
import socket
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app
from sqlalchemy import func

from app.models.archive import (
    ACTIVE_ARCHIVE_STATUSES,
    ARCHIVE_STATUS_CLEANUP_PARTIAL,
    ARCHIVE_STATUS_FAILED,
    ARCHIVE_STATUS_READY,
    ArchiveArtifact,
)
from app.retention.domains import get_archive_domain
from app.retention.service import paginate_archives, preview_retention
from app.storage.service import StorageProfile, build_storage_profile

_ARCHIVE_PER_PAGE_OPTIONS = (5, 10, 25, 50)
_ARCHIVE_STATUS_OPTIONS = (
    "pending",
    "archiving",
    "verifying",
    "cleaning",
    "ready",
    "cleanup_partial",
    "failed",
    "expired",
)
_ARCHIVE_TRIGGER_OPTIONS = ("manual", "scheduled", "cli")
_ARCHIVE_MODE_OPTIONS = ("archive_only", "archive_and_cleanup")
_ARCHIVE_STORAGE_OPTIONS = ("local", "s3")
_STATUS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def build_activity_retention_context(
    *,
    include_preview: bool = False,
    archive_page: int = 1,
    archive_per_page: int = 5,
    archive_status: str = "all",
    archive_trigger: str = "all",
    archive_mode: str = "all",
    archive_storage: str = "all",
    archive_search: str = "",
    feedback: dict[str, Any] | None = None,
    poll_once: bool = False,
) -> dict[str, Any]:
    domain = get_archive_domain("operational_activity")
    policy = domain.build_policy()
    storage_profile = build_storage_profile("archive")
    filters = _normalize_archive_filters(
        status=archive_status,
        trigger_type=archive_trigger,
        operation_mode=archive_mode,
        storage_backend=archive_storage,
        search=archive_search,
    )
    normalized_per_page = (
        archive_per_page if archive_per_page in _ARCHIVE_PER_PAGE_OPTIONS else 5
    )
    archive_pagination = paginate_archives(
        domain_name=domain.name,
        page=archive_page,
        per_page=normalized_per_page,
        status=filters["status"],
        trigger_type=filters["trigger_type"],
        operation_mode=filters["operation_mode"],
        storage_backend=filters["storage_backend"],
        search=filters["search"],
    )
    preview = preview_retention(domain.name) if include_preview else None
    archive_posture = _build_archive_posture(domain.name)
    worker = _cached_status("retention-worker", 12.0, _inspect_retention_worker)
    storage = _build_storage_context(
        storage_profile, archive_posture.get("last_verified")
    )
    schedule_enabled = _bool_config("ACTIVITY_RETENTION_SCHEDULE_ENABLED", True)
    schedule_hour = _int_config("ACTIVITY_RETENTION_SCHEDULE_HOUR", 2)
    schedule_minute = _int_config("ACTIVITY_RETENTION_SCHEDULE_MINUTE", 15)
    schedule_timezone = str(current_app.config.get("CELERY_TIMEZONE", "UTC") or "UTC")

    pagination_total = int(archive_pagination.total or 0)
    pagination_pages = max(int(archive_pagination.pages or 0), 1)

    return {
        "domain": domain.name,
        "enabled": policy.enabled,
        "retention_days": policy.retention_days,
        "archive_retention_days": policy.archive_retention_days,
        "batch_size": policy.batch_size,
        "protect_unreviewed": policy.protect_unreviewed,
        "protected_max_days": policy.protected_max_days,
        "schedule_enabled": schedule_enabled,
        "schedule_hour": schedule_hour,
        "schedule_minute": schedule_minute,
        "schedule_timezone": schedule_timezone,
        "next_schedule_label": _next_schedule_label(
            enabled=schedule_enabled,
            hour=schedule_hour,
            minute=schedule_minute,
            timezone_name=schedule_timezone,
        ),
        "queue_name": str(
            current_app.config.get("RETENTION_CELERY_QUEUE", "inventory") or "inventory"
        ),
        "worker": worker,
        "storage": storage,
        "archive_format": "JSONL.GZ + manifest JSON",
        "preview": _serialize_preview(preview) if preview is not None else None,
        "archives": [_serialize_archive(item) for item in archive_pagination.items],
        "archive_filters": filters,
        "archive_filter_options": {
            "statuses": _ARCHIVE_STATUS_OPTIONS,
            "triggers": _ARCHIVE_TRIGGER_OPTIONS,
            "modes": _ARCHIVE_MODE_OPTIONS,
            "storage_backends": _ARCHIVE_STORAGE_OPTIONS,
        },
        "archive_pagination": {
            "page": archive_pagination.page,
            "pages": pagination_pages,
            "per_page": archive_pagination.per_page,
            "total": pagination_total,
            "start_item": (
                (archive_pagination.page - 1) * archive_pagination.per_page + 1
            )
            if pagination_total
            else 0,
            "end_item": min(
                archive_pagination.page * archive_pagination.per_page, pagination_total
            ),
            "has_prev": archive_pagination.has_prev,
            "has_next": archive_pagination.has_next,
            "prev_num": archive_pagination.prev_num,
            "next_num": archive_pagination.next_num,
            "allowed_per_page": _ARCHIVE_PER_PAGE_OPTIONS,
        },
        "posture": archive_posture,
        "has_active_archives": archive_posture["active_count"] > 0,
        "feedback": feedback,
        "poll_once": bool(poll_once),
    }


def _normalize_archive_filters(
    *,
    status: str,
    trigger_type: str,
    operation_mode: str,
    storage_backend: str,
    search: str,
) -> dict[str, str]:
    normalized_status = status if status in _ARCHIVE_STATUS_OPTIONS else "all"
    normalized_trigger = (
        trigger_type if trigger_type in _ARCHIVE_TRIGGER_OPTIONS else "all"
    )
    normalized_mode = (
        operation_mode if operation_mode in _ARCHIVE_MODE_OPTIONS else "all"
    )
    normalized_storage = (
        storage_backend if storage_backend in _ARCHIVE_STORAGE_OPTIONS else "all"
    )
    return {
        "status": normalized_status,
        "trigger_type": normalized_trigger,
        "operation_mode": normalized_mode,
        "storage_backend": normalized_storage,
        "search": str(search or "").strip(),
    }


def _build_archive_posture(domain_name: str) -> dict[str, Any]:
    domain_query = ArchiveArtifact.query.filter(ArchiveArtifact.domain == domain_name)
    last_run = domain_query.order_by(
        ArchiveArtifact.created_at.desc(),
        ArchiveArtifact.id.desc(),
    ).first()
    last_verified = (
        domain_query.filter(
            ArchiveArtifact.status.in_(
                [ARCHIVE_STATUS_READY, ARCHIVE_STATUS_CLEANUP_PARTIAL]
            ),
            ArchiveArtifact.verified_at.is_not(None),
        )
        .order_by(
            ArchiveArtifact.verified_at.desc(),
            ArchiveArtifact.id.desc(),
        )
        .first()
    )
    active_count = domain_query.filter(
        ArchiveArtifact.status.in_(ACTIVE_ARCHIVE_STATUSES)
    ).count()
    failed_count = domain_query.filter(
        ArchiveArtifact.status == ARCHIVE_STATUS_FAILED
    ).count()
    total_archives = domain_query.count()
    stored_bytes = (
        domain_query.filter(
            ArchiveArtifact.status.in_(
                [ARCHIVE_STATUS_READY, ARCHIVE_STATUS_CLEANUP_PARTIAL]
            )
        )
        .with_entities(func.coalesce(func.sum(ArchiveArtifact.size_bytes), 0))
        .scalar()
        or 0
    )

    return {
        "total_archives": total_archives,
        "active_count": active_count,
        "failed_count": failed_count,
        "stored_bytes": int(stored_bytes),
        "stored_size_label": _format_size(int(stored_bytes)),
        "last_run": _serialize_last_run(last_run),
        "last_verified": last_verified,
        "last_verified_at": last_verified.verified_at if last_verified else None,
    }


def _serialize_last_run(artifact: ArchiveArtifact | None) -> dict[str, Any] | None:
    if artifact is None:
        return None
    return {
        "id": artifact.id,
        "status": artifact.status,
        "trigger_type": artifact.trigger_type,
        "operation_mode": artifact.operation_mode,
        "record_count": artifact.record_count,
        "cleanup_deleted_count": artifact.cleanup_deleted_count,
        "created_at": artifact.created_at,
        "completed_at": artifact.completed_at,
    }


def _serialize_preview(preview: dict[str, Any]) -> dict[str, Any]:
    boundary = preview["boundary"]
    return {
        "record_count": boundary.record_count,
        "cutoff_at": boundary.cutoff_at,
        "range_start": boundary.range_start,
        "range_end": boundary.range_end,
        "maximum_record_id": boundary.maximum_record_id,
        "protected_record_count": boundary.protected_record_count,
        "estimated_uncompressed_bytes": preview["estimated_uncompressed_bytes"],
        "estimated_size_label": _format_size(preview["estimated_uncompressed_bytes"]),
    }


def _serialize_archive(artifact: ArchiveArtifact) -> dict[str, Any]:
    metadata = artifact.metadata_json or {}
    storage_locator = (
        metadata.get("storage_locator") if isinstance(metadata, dict) else None
    )
    return {
        "id": artifact.id,
        "short_id": artifact.id.split("-")[0],
        "status": artifact.status,
        "trigger_type": artifact.trigger_type,
        "operation_mode": artifact.operation_mode,
        "record_count": artifact.record_count,
        "cleanup_deleted_count": artifact.cleanup_deleted_count,
        "storage_backend": artifact.storage_backend,
        "storage_label": _archive_storage_label(
            artifact.storage_backend, storage_locator
        ),
        "size_bytes": artifact.size_bytes,
        "size_label": _format_size(artifact.size_bytes),
        "checksum_sha256": artifact.checksum_sha256,
        "checksum_short": artifact.checksum_sha256[:12]
        if artifact.checksum_sha256
        else None,
        "range_start": artifact.range_start,
        "range_end": artifact.range_end,
        "created_at": artifact.created_at,
        "completed_at": artifact.completed_at,
        "verified_at": artifact.verified_at,
        "error_message": artifact.error_message,
        "error_summary": _archive_error_summary(artifact.error_message),
        "celery_task_id": artifact.celery_task_id,
        "is_downloadable": artifact.is_downloadable,
        "is_verifiable": artifact.is_verifiable,
    }


def _build_storage_context(
    profile: StorageProfile,
    last_verified: ArchiveArtifact | None,
) -> dict[str, Any]:
    provider = _storage_provider_label(profile.backend, profile.s3_endpoint_url)
    verified_artifact = (
        last_verified
        if _artifact_matches_storage_profile(last_verified, profile)
        else None
    )
    status = "configured"
    status_label = "Configured"
    status_tone = "blue"
    detail = (
        "Archive target is configured and will be verified during every lifecycle run."
    )

    if profile.backend == "local":
        root = Path(profile.local_root)
        try:
            root.mkdir(parents=True, exist_ok=True)
            writable = root.is_dir() and os.access(root, os.W_OK | os.X_OK)
        except OSError:
            writable = False
        if writable:
            status = "ready"
            status_label = "Ready"
            status_tone = "emerald"
            detail = "The local archive directory is available to the application."
        else:
            status = "unavailable"
            status_label = "Unavailable"
            status_tone = "rose"
            detail = "The local archive directory is not available to the application."
    elif not profile.s3_bucket:
        status = "incomplete"
        status_label = "Incomplete"
        status_tone = "amber"
        detail = "An S3-compatible bucket is required before archive jobs can run."
    elif verified_artifact is not None and verified_artifact.storage_backend == "s3":
        status = "verified"
        status_label = "Verified"
        status_tone = "emerald"
        detail = "A previous archive was uploaded and checksum-verified on this S3-compatible backend."
    elif profile.s3_endpoint_url:
        endpoint_probe = _cached_status(
            f"archive-storage:{profile.s3_endpoint_url}",
            20.0,
            lambda: _probe_storage_endpoint(profile.s3_endpoint_url),
        )
        if endpoint_probe["reachable"]:
            status = "reachable"
            status_label = "Reachable"
            status_tone = "emerald"
            detail = "The configured S3-compatible endpoint is reachable from the KAORI web container."
        else:
            status = "unreachable"
            status_label = "Unreachable"
            status_tone = "rose"
            detail = endpoint_probe["detail"]

    return {
        "backend": profile.backend,
        "provider_label": provider,
        "status": status,
        "status_label": status_label,
        "status_tone": status_tone,
        "detail": detail,
        "location": _storage_location(profile),
        "endpoint_label": _storage_endpoint_label(profile),
        "bucket": profile.s3_bucket if profile.backend == "s3" else None,
        "last_verified_at": verified_artifact.verified_at
        if verified_artifact
        else None,
    }


def _artifact_matches_storage_profile(
    artifact: ArchiveArtifact | None,
    profile: StorageProfile,
) -> bool:
    if artifact is None or artifact.storage_backend != profile.backend:
        return False
    metadata = artifact.metadata_json or {}
    locator = metadata.get("storage_locator") if isinstance(metadata, dict) else None
    if not isinstance(locator, dict):
        return False
    if profile.backend == "local":
        archived_root = str(locator.get("local_root") or "").strip()
        return (
            bool(archived_root)
            and Path(archived_root).resolve() == profile.local_root.resolve()
        )
    return (
        str(locator.get("s3_bucket") or "").strip() == profile.s3_bucket
        and str(locator.get("s3_endpoint_url") or "").strip().rstrip("/")
        == str(profile.s3_endpoint_url or "").strip().rstrip("/")
        and str(locator.get("s3_prefix") or "").strip().strip("/") == profile.s3_prefix
    )


def _probe_storage_endpoint(endpoint_url: str) -> dict[str, Any]:
    parsed = urlparse(endpoint_url)
    host = parsed.hostname
    if not host:
        return {
            "reachable": False,
            "detail": "Archive storage configuration is invalid.",
        }
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=0.6):
            return {
                "reachable": True,
                "detail": f"{host}:{port} accepted a TCP connection.",
            }
    except OSError:
        return {
            "reachable": False,
            "detail": "Archive storage is currently unavailable.",
        }


def _inspect_retention_worker() -> dict[str, Any]:
    queue_name = str(
        current_app.config.get("RETENTION_CELERY_QUEUE", "inventory") or "inventory"
    )
    celery_app = current_app.extensions.get("celery")
    if celery_app is None:
        return {
            "status": "unavailable",
            "label": "Unavailable",
            "tone": "rose",
            "count": 0,
            "queue_ready": False,
            "detail": "Celery is not initialized in the web application.",
            "worker_names": [],
        }

    try:
        inspector = celery_app.control.inspect(timeout=0.75)
        queue_map = inspector.active_queues() or {}
        if not queue_map:
            ping_map = inspector.ping() or {}
            if not ping_map:
                return {
                    "status": "offline",
                    "label": "Offline",
                    "tone": "rose",
                    "count": 0,
                    "queue_ready": False,
                    "detail": "No Celery worker responded to the health inspection.",
                    "worker_names": [],
                }
            queue_map = {name: [] for name in ping_map}

        worker_names = sorted(queue_map.keys())
        queue_ready = any(
            any(str(queue.get("name") or "") == queue_name for queue in queues or [])
            for queues in queue_map.values()
        )
        if queue_ready:
            return {
                "status": "online",
                "label": "Online",
                "tone": "emerald",
                "count": len(worker_names),
                "queue_ready": True,
                "detail": f"{len(worker_names)} worker(s) are listening on the {queue_name} queue.",
                "worker_names": worker_names,
            }
        return {
            "status": "queue_mismatch",
            "label": "Queue mismatch",
            "tone": "amber",
            "count": len(worker_names),
            "queue_ready": False,
            "detail": f"Workers responded, but none reported the {queue_name} queue.",
            "worker_names": worker_names,
        }
    except Exception as exc:
        current_app.logger.warning("Could not inspect retention Celery worker: %s", exc)
        return {
            "status": "unknown",
            "label": "Unknown",
            "tone": "slate",
            "count": 0,
            "queue_ready": False,
            "detail": f"Worker health inspection failed with {type(exc).__name__}.",
            "worker_names": [],
        }


def _cached_status(
    key: str,
    ttl_seconds: float,
    loader: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    now = monotonic()
    cached = _STATUS_CACHE.get(key)
    if cached and now - cached[0] < ttl_seconds:
        return dict(cached[1])
    value = loader()
    _STATUS_CACHE[key] = (now, dict(value))
    return value


def _next_schedule_label(
    *,
    enabled: bool,
    hour: int,
    minute: int,
    timezone_name: str,
) -> str | None:
    if not enabled:
        return None
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone = UTC
    now = datetime.now(timezone)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate.strftime("%d %b %Y %H:%M %Z")


def _storage_provider_label(backend: str, endpoint_url: str | None) -> str:
    if backend == "local":
        return "Local filesystem"
    endpoint = str(endpoint_url or "").strip().lower()
    hostname = (urlparse(endpoint).hostname or "").lower() if endpoint else ""
    if (
        "minio" in endpoint
        or hostname.startswith("minio")
        or ":9000" in endpoint
        or ":9001" in endpoint
    ):
        return "MinIO"
    if not endpoint or "amazonaws.com" in endpoint:
        return "Amazon S3"
    return "S3-compatible"


def _archive_storage_label(backend: str | None, locator: Any) -> str:
    normalized_backend = str(backend or "").strip().lower()
    if normalized_backend == "local":
        return "Local filesystem"
    if normalized_backend != "s3":
        return normalized_backend.upper() if normalized_backend else "-"
    endpoint = None
    if isinstance(locator, dict):
        endpoint = locator.get("s3_endpoint_url")
    return _storage_provider_label("s3", str(endpoint) if endpoint else None)


def _storage_endpoint_label(profile: StorageProfile) -> str | None:
    if profile.backend == "local":
        return None
    endpoint = str(profile.s3_endpoint_url or "").strip()
    if not endpoint:
        return "AWS endpoint"
    parsed = urlparse(endpoint)
    return parsed.netloc or endpoint


def _storage_location(profile: StorageProfile) -> str:
    if profile.backend == "local":
        return str(profile.local_root)
    prefix = f"/{profile.s3_prefix}" if profile.s3_prefix else ""
    return f"s3://{profile.s3_bucket}{prefix}"


def _bool_config(key: str, default: bool) -> bool:
    value = current_app.config.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_config(key: str, default: int) -> int:
    try:
        return int(current_app.config.get(key, default))
    except (TypeError, ValueError):
        return default


def _archive_error_summary(message: str | None) -> str | None:
    normalized = str(message or "").strip()
    if not normalized:
        return None

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

    return "Archive lifecycle failed. Review Activity Audit Log for details."


def _format_size(value: int | None) -> str:
    size = float(value or 0)
    units = ("B", "KB", "MB", "GB", "TB")
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024
    return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"

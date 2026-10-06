from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func

from app.models.archive import (
    ACTIVE_ARCHIVE_STATUSES,
    ARCHIVE_STATUS_FAILED,
    ARCHIVE_STATUS_PURGE_FAILED,
    ArchiveArtifact,
)
from app.models.job import JobExecution
from app.models.lifecycle import DataLifecyclePolicy
from app.platform_operations.data_lifecycle.retention.domains import DOMAIN_FACTORIES
from app.platform_operations.data_lifecycle.retention.presentation import build_data_lifecycle_context


def build_workspace_context(
    *,
    selected_domain: str,
    active_tab: str,
    include_preview: bool,
    archive_page: int,
    archive_per_page: int,
    archive_status: str,
    archive_trigger: str,
    archive_mode: str,
    archive_storage: str,
    archive_search: str,
    archive_domain: str,
    feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Platform Operations projection over the shared retention engine."""

    return build_data_lifecycle_context(
        selected_domain=selected_domain,
        active_tab=active_tab,
        include_preview=include_preview,
        archive_page=archive_page,
        archive_per_page=archive_per_page,
        archive_status=archive_status,
        archive_trigger=archive_trigger,
        archive_mode=archive_mode,
        archive_storage=archive_storage,
        archive_search=archive_search,
        archive_domain=archive_domain,
        feedback=feedback,
    )


def build_data_lifecycle_overview_summary() -> dict[str, int]:
    """Return a DB-only lifecycle posture projection for Platform Operations Overview."""

    supported = tuple(sorted(DOMAIN_FACTORIES))
    stored = {
        item.domain: item for item in DataLifecyclePolicy.query.filter(DataLifecyclePolicy.domain.in_(supported)).all()
    }
    enabled_domain_count = sum(int(bool(item.enabled)) for item in stored.values())

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    archive_summary = (
        ArchiveArtifact.query.filter(ArchiveArtifact.domain.in_(supported))
        .with_entities(
            func.sum(case((ArchiveArtifact.status.in_(tuple(ACTIVE_ARCHIVE_STATUSES)), 1), else_=0)).label('active'),
            func.sum(
                case(
                    (
                        ArchiveArtifact.status.in_((ARCHIVE_STATUS_FAILED, ARCHIVE_STATUS_PURGE_FAILED))
                        & (ArchiveArtifact.updated_at >= cutoff),
                        1,
                    ),
                    else_=0,
                )
            ).label('failed_24h'),
        )
        .one()
    )
    active_archive_total = int(archive_summary.active or 0)
    failed_archive_24h = int(archive_summary.failed_24h or 0)
    active_job_total = JobExecution.query.filter(
        JobExecution.job_type == 'data_lifecycle',
        JobExecution.status.in_(('queued', 'running', 'retrying', 'cancel_requested')),
    ).count()

    return {
        'managed_domain_count': len(supported),
        'enabled_domain_count': int(enabled_domain_count),
        'active_archive_total': active_archive_total,
        'failed_archive_24h': failed_archive_24h,
        'active_job_total': int(active_job_total or 0),
    }

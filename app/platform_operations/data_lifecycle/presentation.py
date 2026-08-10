from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.archive import ACTIVE_ARCHIVE_STATUSES, ARCHIVE_STATUS_FAILED, ArchiveArtifact
from app.models.job import JobExecution
from app.models.lifecycle import DataLifecyclePolicy
from app.retention.domains import DOMAIN_FACTORIES, get_archive_domain
from app.retention.presentation import build_data_lifecycle_context


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
    enabled_domain_count = 0
    for domain_name in supported:
        policy = stored.get(domain_name)
        if policy is not None:
            enabled_domain_count += int(bool(policy.enabled))
            continue
        enabled_domain_count += int(bool(get_archive_domain(domain_name).build_policy().enabled))

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    active_archive_total = ArchiveArtifact.query.filter(
        ArchiveArtifact.domain.in_(supported),
        ArchiveArtifact.status.in_(tuple(ACTIVE_ARCHIVE_STATUSES)),
    ).count()
    failed_archive_24h = ArchiveArtifact.query.filter(
        ArchiveArtifact.domain.in_(supported),
        ArchiveArtifact.status == ARCHIVE_STATUS_FAILED,
        ArchiveArtifact.updated_at >= cutoff,
    ).count()
    active_job_total = JobExecution.query.filter(
        JobExecution.job_type == 'data_lifecycle',
        JobExecution.status.in_(('queued', 'running', 'retrying', 'cancel_requested')),
    ).count()

    return {
        'managed_domain_count': len(supported),
        'enabled_domain_count': int(enabled_domain_count),
        'active_archive_total': int(active_archive_total or 0),
        'failed_archive_24h': int(failed_archive_24h or 0),
        'active_job_total': int(active_job_total or 0),
    }

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from flask import request, url_for

from app.analytics.materialization.requests import MaterializedRequest


def snapshot_meta(materialized: MaterializedRequest) -> dict[str, Any]:
    snapshot = materialized.result.snapshot
    return {
        'state': materialized.result.state,
        'stale': materialized.result.stale,
        'refresh_dispatched': materialized.dispatched,
        'generated_at': snapshot.generated_at if snapshot else None,
        'expires_at': snapshot.expires_at if snapshot else None,
        'last_error': snapshot.last_error if snapshot else None,
        'source_warning': materialized.source_warning,
    }


def materialization_progress_context(snapshot: Any) -> dict[str, Any]:
    """Return a complete, render-safe progress context for one snapshot."""
    progress_message = None
    progress_percent = None
    materialization_error = snapshot.last_error if snapshot else None

    if snapshot is not None and snapshot.last_job_execution_id is not None:
        from app.models.job import JobExecution

        job = JobExecution.query.get(snapshot.last_job_execution_id)
        if job is not None:
            progress_message = job.progress_message
            if job.progress_total and job.progress_total > 0:
                progress_percent = min(
                    100,
                    max(
                        0,
                        round(
                            (job.progress_current or 0)
                            / job.progress_total
                            * 100
                        ),
                    ),
                )
            if job.is_terminal and snapshot.status != 'ready' and not materialization_error:
                materialization_error = (
                    job.error_message
                    or (
                        'The background job completed without producing the requested analytics snapshot.'
                        if job.status in {'succeeded', 'partial'}
                        else (
                            'Analytics preparation ended with status '
                            f'{job.status.replace("_", " ").title()}.'
                        )
                    )
                )

    return {
        'materialization_error': materialization_error,
        'materialization_progress_message': progress_message,
        'materialization_progress_percent': progress_percent,
    }


def pending_page_context(
    *,
    materialized: MaterializedRequest,
    dataset_key: str,
    title: str,
    description: str,
    icon: str,
    page_id: str | None = None,
) -> dict[str, Any]:
    parameters = dict(materialized.parameters)
    return_url = request.full_path.rstrip('?')
    status_query = urlencode(
        {
            'dataset_key': dataset_key,
            'cluster_id': materialized.cluster.id if materialized.cluster else '',
            'return_url': return_url,
            **parameters,
        }
    )
    snapshot = materialized.result.snapshot
    progress = materialization_progress_context(snapshot)
    if materialized.dispatch_error:
        progress['materialization_error'] = materialized.dispatch_error

    return {
        'materialization_title': title,
        'materialization_description': description,
        'materialization_icon': icon,
        'materialization_page_id': page_id or 'analytics-materialization-page',
        'materialization_cluster': materialized.cluster,
        'materialization_state': materialized.result.state,
        'materialization_status_url': f'{url_for("analytics.materialization_status")}?{status_query}',
        'materialization_return_url': return_url,
        **progress,
    }


def blocked_page_context(
    *,
    materialized: MaterializedRequest,
    title: str,
    description: str,
    icon: str,
    page_id: str,
) -> dict[str, Any]:
    """Build a full-page dependency state without invoking an integration client."""
    return {
        'materialization_title': title,
        'materialization_description': description,
        'materialization_icon': icon,
        'materialization_page_id': page_id,
        'materialization_cluster': materialized.cluster,
        'dependency_blocker': materialized.dependency_blocker,
    }

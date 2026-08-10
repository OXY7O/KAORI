from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from flask import request, url_for

from app.analytics.materialization.requests import MaterializedRequest


_FAILURE_PATTERN = re.compile(
    r'^\[(?P<code>[^]]+)]\s+(?P<title>.*?):\s+(?P<detail>.*?)'
    r'(?:\s+Recommended action:\s+(?P<remediation>.*))?$',
    re.DOTALL,
)


def parse_materialization_error(value: str | None) -> dict[str, Any]:
    """Parse the worker failure contract into render-safe UI fields."""

    message = str(value or '').strip()
    if not message:
        return {
            'message': None,
            'code': None,
            'title': None,
            'detail': None,
            'remediation': None,
        }
    match = _FAILURE_PATTERN.match(message)
    if match is None:
        return {
            'message': message,
            'code': None,
            'title': 'Analytics Data Preparation Failed',
            'detail': message,
            'remediation': None,
        }
    fields = {key: (item.strip() if item else None) for key, item in match.groupdict().items()}
    return {
        'message': message,
        'code': fields['code'],
        'title': fields['title'],
        'detail': fields['detail'],
        'remediation': fields['remediation'],
    }


def snapshot_meta(materialized: MaterializedRequest) -> dict[str, Any]:
    snapshot = materialized.result.snapshot
    context = materialized.result.context or {}
    runtime = context.get('analytics_runtime') if isinstance(context, dict) else None
    failure = parse_materialization_error(snapshot.last_error if snapshot else None)
    return {
        'state': materialized.result.state,
        'status': snapshot.status if snapshot else materialized.result.state,
        'dataset_key': snapshot.dataset_key if snapshot else None,
        'stale': materialized.result.stale,
        'refresh_dispatched': materialized.dispatched,
        'generated_at': snapshot.generated_at if snapshot else None,
        'expires_at': snapshot.expires_at if snapshot else None,
        'last_attempt_at': snapshot.last_attempt_at if snapshot else None,
        'last_job_execution_id': snapshot.last_job_execution_id if snapshot else None,
        'last_error': snapshot.last_error if snapshot else None,
        'last_error_code': failure['code'],
        'last_error_title': failure['title'],
        'last_error_detail': failure['detail'],
        'last_error_remediation': failure['remediation'],
        'source_warning': materialized.source_warning,
        'runtime': runtime if isinstance(runtime, dict) else None,
    }


def materialization_progress_context(snapshot: Any) -> dict[str, Any]:
    """Return a complete, render-safe progress context for one snapshot."""
    progress_message = None
    progress_percent = None
    job = None
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
                        round((job.progress_current or 0) / job.progress_total * 100),
                    ),
                )
            if job.is_terminal and snapshot.status != 'ready' and not materialization_error:
                materialization_error = job.error_message or (
                    'The background job completed without producing the requested analytics snapshot.'
                    if job.status in {'succeeded', 'partially_succeeded'}
                    else (f'Analytics preparation ended with status {job.status.replace("_", " ").title()}.')
                )

    failure = parse_materialization_error(materialization_error)
    materialization_error = failure['message']
    return {
        'materialization_error': materialization_error,
        'materialization_error_code': failure['code'] or (job.error_code if job else None),
        'materialization_error_title': failure['title'],
        'materialization_error_detail': failure['detail'],
        'materialization_error_remediation': failure['remediation'],
        'materialization_progress_message': progress_message,
        'materialization_progress_percent': progress_percent,
        'materialization_job_public_id': job.public_id if job else None,
        'materialization_job_status': job.status if job else None,
        'materialization_job_queue': job.queue_name if job else None,
        'materialization_job_attempt': job.attempt_count if job else None,
        'materialization_job_url': (
            url_for(
                'jobs.executions',
                execution_tab='registry',
                queue=job.queue_name or '',
                search=job.public_id,
            )
            if job is not None
            else None
        ),
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
        failure = parse_materialization_error(materialized.dispatch_error)
        progress.update(
            {
                'materialization_error': failure['message'],
                'materialization_error_code': failure['code'],
                'materialization_error_title': failure['title'],
                'materialization_error_detail': failure['detail'],
                'materialization_error_remediation': failure['remediation'],
            }
        )

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

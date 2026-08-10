from __future__ import annotations

import json
from typing import Any

from app.common.presentation import present_user_datetime
from app.common.job_execution_contract import job_operation_label
from app.models.job import JobExecution

_JOB_ICONS = {
    'runtime': 'activity',
    'validation': 'scan-search',
    'analytics': 'chart-no-axes-combined',
    'forecasting': 'chart-spline',
    'standard': 'workflow',
}

_STATUS_PRESENTATION = {
    'queued': ('Queued', 'pending', 'clock-3'),
    'running': ('Running', 'pending', 'loader-circle'),
    'retrying': ('Retrying', 'warning', 'rotate-ccw'),
    'cancel_requested': ('Cancel Requested', 'warning', 'octagon-alert'),
    'succeeded': ('Succeeded', 'normal', 'circle-check'),
    'partially_succeeded': ('Partially Succeeded', 'warning', 'triangle-alert'),
    'failed': ('Failed', 'critical', 'circle-x'),
    'canceled': ('Canceled', 'unknown', 'ban'),
    'expired': ('Expired', 'unknown', 'clock-alert'),
}


def _duration_label(job: JobExecution) -> str:
    if job.status == 'queued':
        return 'Waiting'
    start = job.started_at or job.queued_at
    end = job.completed_at
    if start is None:
        return 'Not started'
    if end is None:
        return 'In progress'
    seconds = max(int((end - start).total_seconds()), 0)
    if seconds < 60:
        return f'{seconds}s'
    minutes, remaining = divmod(seconds, 60)
    if minutes < 60:
        return f'{minutes}m {remaining}s'
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes}m'


def present_job_execution_row(job: JobExecution) -> dict[str, Any]:
    """Build canonical job identity, state, timing, and progress presentation."""
    total = max(job.progress_total, 0)
    current = max(job.progress_current, 0)
    progress = (
        min(int((current / total) * 100), 100)
        if total
        else (100 if job.is_terminal else 0)
    )
    if total > 0 or job.is_terminal:
        progress_mode = 'determinate'
        progress_label = f'{progress}%'
    elif job.status == 'queued':
        progress_mode = 'queued'
        progress_label = 'Queued'
    else:
        progress_mode = 'indeterminate'
        progress_label = 'In Progress'

    requester = (
        job.requested_by.display_label
        if job.requested_by is not None
        else 'KAORI Scheduler'
    )
    status_label, status_tone, status_icon = _STATUS_PRESENTATION.get(
        job.status,
        (job.status.replace('_', ' ').title(), 'unknown', 'circle-help'),
    )
    scope = job.scope_key or (
        f'{job.provider_type}:{job.provider_instance_id}'
        if job.provider_type and job.provider_instance_id is not None
        else job.resource_group or 'Global'
    )
    return {
        'public_id': job.public_id,
        'task_id': job.celery_task_id,
        'job_type': job.job_type,
        'operation': job.operation,
        'operation_label': job_operation_label(job.operation),
        'workload_class': job.workload_class,
        'workload_label': job.workload_class.replace('_', ' ').title(),
        'icon': _JOB_ICONS.get(job.workload_class, 'workflow'),
        'queue_name': job.queue_name,
        'priority': job.priority,
        'status': job.status,
        'status_label': status_label,
        'status_tone': status_tone,
        'status_icon': status_icon,
        'provider_type': job.provider_type,
        'provider_label': (job.provider_type or 'KAORI').replace('_', ' ').title(),
        'scope': scope,
        'resource_group': job.resource_group,
        'requester': requester,
        'progress': progress,
        'progress_mode': progress_mode,
        'progress_label': progress_label,
        'progress_current': current,
        'progress_total': total,
        'progress_message': job.progress_message or 'Waiting for worker',
        'attempt_count': job.attempt_count,
        'max_attempts': job.max_attempts,
        'queued_at': present_user_datetime(job.queued_at, empty='Not queued'),
        'started_at': present_user_datetime(job.started_at, empty='Not started'),
        'completed_at': present_user_datetime(job.completed_at, empty='In progress'),
        'updated_at': present_user_datetime(job.updated_at, empty='Not updated'),
        'duration': _duration_label(job),
        'error_message': job.error_message,
        'is_active': job.is_active,
        'is_terminal': job.is_terminal,
    }


def present_job_execution(job: JobExecution) -> dict[str, Any]:
    """Return compact execution presentation for Deck and configuration workspaces."""
    row = present_job_execution_row(job)
    payload = job.payload_json or {}
    trigger_type = str(
        payload.get('trigger_type')
        or ('scheduled' if job.requested_by_user_id is None else 'manual')
    )
    row.update(
        {
            'trigger_type': trigger_type,
            'trigger_label': trigger_type.replace('_', ' ').title(),
            'trigger_icon': (
                'calendar-clock' if trigger_type == 'scheduled' else 'mouse-pointer-click'
            ),
            'target_count': int(
                payload.get('target_count')
                or payload.get('total_count')
                or payload.get('work_item_count')
                or job.progress_total
                or 0
            ),
        }
    )
    return row


def _present_result_summary(summary: dict[str, Any] | None) -> tuple[list[dict[str, str]], int]:
    if not isinstance(summary, dict) or not summary:
        return [], 0

    rows: list[dict[str, str]] = []
    for key, value in sorted(summary.items(), key=lambda item: str(item[0])):
        if isinstance(value, (dict, list, tuple)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        elif value is None:
            rendered = '-'
        elif isinstance(value, bool):
            rendered = 'Yes' if value else 'No'
        else:
            rendered = str(value)
        rows.append(
            {
                'label': str(key).replace('_', ' ').replace('-', ' ').title(),
                'value': rendered,
            }
        )

    visible_rows = rows[:12]
    return visible_rows, max(len(rows) - len(visible_rows), 0)


def present_job_execution_detail(job: JobExecution) -> dict[str, Any]:
    """Return safe operator-facing execution evidence without exposing raw request payloads."""
    row = present_job_execution(job)
    result_summary, result_summary_remaining = _present_result_summary(job.result_summary_json)
    row.update(
        {
            'scope_type': (job.scope_type or 'global').replace('_', ' ').title(),
            'provider_instance': str(job.provider_instance_id) if job.provider_instance_id is not None else '-',
            'resource_group': job.resource_group or '-',
            'parent_public_id': job.parent.public_id if job.parent is not None else '-',
            'heartbeat_at': present_user_datetime(job.heartbeat_at, empty='No heartbeat recorded'),
            'cancel_requested_at': present_user_datetime(
                job.cancel_requested_at,
                empty='Not requested',
            ),
            'expires_at': present_user_datetime(job.expires_at, empty='No expiry recorded'),
            'created_at': present_user_datetime(job.created_at, empty='Not recorded'),
            'error_code': job.error_code or '-',
            'error_message': job.error_message or 'No execution error was recorded.',
            'result_type': (job.result_type or '-').replace('_', ' ').title() if job.result_type else '-',
            'result_reference': job.result_reference or '-',
            'result_summary': result_summary,
            'result_summary_remaining': result_summary_remaining,
        }
    )
    return row

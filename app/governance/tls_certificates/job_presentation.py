from __future__ import annotations

from datetime import UTC
from typing import Any

from sqlalchemy import or_

from app.common.presentation import present_user_datetime
from app.governance.tls_certificates.constants import TLS_SYNC_JOB_TYPE, TLS_SYNC_OPERATION
from app.models.job import JobExecution, JobExecutionSubscriber


def _visible_query(user_id: int):
    subscriber_can_view = JobExecution.subscribers.any(
        JobExecutionSubscriber.user_id == user_id,
    )
    return JobExecution.query.filter(
        JobExecution.job_type == TLS_SYNC_JOB_TYPE,
        JobExecution.operation == TLS_SYNC_OPERATION,
        or_(
            JobExecution.requested_by_user_id == user_id,
            subscriber_can_view,
        ),
    )


def get_visible_tls_sync_job(*, public_id: str, user_id: int) -> JobExecution | None:
    return _visible_query(user_id).filter(JobExecution.public_id == public_id).first()


def _duration_seconds(job: JobExecution) -> int | None:
    started_at = job.started_at or job.queued_at
    finished_at = job.completed_at
    if started_at is None or finished_at is None:
        return None
    started = started_at.replace(tzinfo=UTC) if started_at.tzinfo is None else started_at.astimezone(UTC)
    finished = finished_at.replace(tzinfo=UTC) if finished_at.tzinfo is None else finished_at.astimezone(UTC)
    return max(int((finished - started).total_seconds()), 0)


def _active_status(job: JobExecution) -> tuple[str, str]:
    if job.status == 'queued':
        return 'Queued', 'Waiting for the inventory worker to start TLS Secret collection.'
    if job.status == 'retrying':
        return 'Retrying', job.progress_message or 'Retrying TLS Secret collection in the inventory worker.'
    if job.status == 'cancel_requested':
        return 'Canceling', job.progress_message or 'Waiting for the inventory worker to stop safely.'
    return 'Running', job.progress_message or 'Collecting Kubernetes TLS Secrets.'


def _terminal_status(job: JobExecution) -> tuple[str, str, str]:
    if job.status == 'succeeded':
        return 'success', 'TLS Secret Sync Completed', 'Completed'
    if job.status == 'partially_succeeded':
        return 'warning', 'TLS Secret Sync Completed With Warnings', 'Completed With Warnings'
    if job.status == 'canceled':
        return 'warning', 'TLS Secret Sync Canceled', 'Canceled'
    if job.status == 'expired':
        return 'error', 'TLS Secret Sync Expired', 'Expired'
    return 'error', 'TLS Secret Sync Failed', 'Failed'


def present_tls_sync_job(job: JobExecution, *, user_id: int | None = None) -> dict[str, Any]:
    total = max(int(job.progress_total or 0), 0)
    current = max(int(job.progress_current or 0), 0)
    progress_percent = min(int((current / total) * 100), 100) if total else 0
    payload = job.payload_json or {}
    target_count = int(payload.get('target_count') or total or 0)

    if job.is_active:
        status_label, message = _active_status(job)
        return {
            'public_id': job.public_id,
            'is_active': True,
            'status_label': status_label,
            'message': message,
            'progress_current': current,
            'progress_total': total,
            'progress_percent': progress_percent,
            'target_count': target_count,
            'progress_text': (f'{progress_percent}% · {target_count} target cluster{"s" if target_count != 1 else ""}'),
        }

    status, title, status_label = _terminal_status(job)
    result = job.result_summary_json or {}
    successful_count = int(result.get('successful_cluster_count') or 0)
    failed_count = int(result.get('failed_cluster_count') or 0)
    warning_count = int(result.get('warning_cluster_count') or 0)
    collected_count = int(result.get('collected_count') or 0)
    result_target_count = int(result.get('target_count') or target_count or successful_count + failed_count)

    if job.status in {'succeeded', 'partially_succeeded'}:
        message = (
            f'{collected_count} TLS Secrets were collected across '
            f'{successful_count} cluster{"s" if successful_count != 1 else ""}.'
        )
        if failed_count and warning_count:
            detail = (
                f'{failed_count} cluster syncs failed and {warning_count} completed with '
                'incomplete Ingress mapping evidence.'
            )
        elif failed_count:
            detail = f'{failed_count} cluster syncs require review in Jobs & Executions.'
        elif warning_count:
            detail = (
                f'{warning_count} cluster syncs completed with incomplete Ingress mapping '
                'evidence. Review collection evidence before relying on host coverage.'
            )
        else:
            detail = 'Certificate expiry, SAN coverage, and Ingress usage are now current.'
    elif job.status == 'canceled':
        message = 'TLS Secret collection was canceled before completion.'
        detail = job.progress_message or 'Review Jobs & Executions for the final worker state.'
    else:
        message = 'KAORI could not complete TLS Secret collection.'
        detail = job.error_message or job.progress_message or 'Review Jobs & Executions before retrying.'

    notification_deck_user_ids = {
        int(value) for value in (result.get('notification_deck_user_ids') or []) if str(value).isdigit()
    }
    activity_audit_saved = bool(result.get('activity_audit_saved'))
    notification_deck_visible = user_id is not None and int(user_id) in notification_deck_user_ids

    return {
        'public_id': job.public_id,
        'is_active': False,
        'status': status,
        'title': title,
        'status_label': status_label,
        'message': message,
        'detail': detail,
        'total_count': result_target_count,
        'synced_count': successful_count,
        'failed_count': failed_count or (result_target_count if status == 'error' else 0),
        'warning_count': warning_count,
        'duration_seconds': _duration_seconds(job),
        'completed_label': present_user_datetime(job.completed_at, empty='Completed just now'),
        'activity_audit_saved': activity_audit_saved,
        'notification_deck_visible': notification_deck_visible,
    }

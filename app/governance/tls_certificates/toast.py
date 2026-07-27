from __future__ import annotations

from datetime import UTC
from typing import Any

from sqlalchemy import or_

from app.common.presentation import present_user_datetime
from app.governance.tls_certificates.sync_jobs import TLS_SYNC_JOB_TYPE, TLS_SYNC_OPERATION
from app.jobs.constants import ACTIVE_JOB_STATUSES
from app.models.job import JobExecution, JobExecutionSubscriber


def _visible_query(user_id: int):
    return (
        JobExecution.query.outerjoin(
            JobExecutionSubscriber,
            JobExecutionSubscriber.job_execution_id == JobExecution.id,
        )
        .filter(
            JobExecution.job_type == TLS_SYNC_JOB_TYPE,
            JobExecution.operation == TLS_SYNC_OPERATION,
            or_(
                JobExecution.requested_by_user_id == user_id,
                JobExecutionSubscriber.user_id == user_id,
            ),
        )
        .distinct()
    )


def get_visible_tls_sync_job(*, public_id: str, user_id: int) -> JobExecution | None:
    return _visible_query(user_id).filter(JobExecution.public_id == public_id).first()


def get_active_tls_sync_job(*, user_id: int) -> JobExecution | None:
    return (
        _visible_query(user_id)
        .filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )


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


def present_tls_sync_toast(job: JobExecution) -> dict[str, Any]:
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
        }

    status, title, status_label = _terminal_status(job)
    result = job.result_summary_json or {}
    successful_count = int(result.get('successful_cluster_count') or 0)
    failed_count = int(result.get('failed_cluster_count') or 0)
    collected_count = int(result.get('collected_count') or 0)
    result_target_count = int(result.get('target_count') or target_count or successful_count + failed_count)

    if job.status in {'succeeded', 'partially_succeeded'}:
        message = (
            f'{collected_count} TLS Secrets were collected across '
            f'{successful_count} cluster{"s" if successful_count != 1 else ""}.'
        )
        detail = (
            f'{failed_count} cluster syncs require review in Jobs & Executions.'
            if failed_count
            else 'Certificate expiry, SAN coverage, and Ingress usage are now current.'
        )
    elif job.status == 'canceled':
        message = 'TLS Secret collection was canceled before completion.'
        detail = job.progress_message or 'Review Jobs & Executions for the final worker state.'
    else:
        message = 'KAORI could not complete TLS Secret collection.'
        detail = job.error_message or job.progress_message or 'Review Jobs & Executions before retrying.'

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
        'duration_seconds': _duration_seconds(job),
        'completed_label': present_user_datetime(job.completed_at, empty='Completed just now'),
    }

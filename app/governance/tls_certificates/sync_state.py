from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.common.presentation import present_user_datetime
from app.jobs.constants import ACTIVE_JOB_STATUSES
from app.jobs.policies.service import get_or_create_job_policy
from app.models.governance import TLSCertificateInventory
from app.models.job import JobExecution

from .sync_jobs import TLS_SYNC_JOB_TYPE, TLS_SYNC_OPERATION

_SUCCESS_STATUSES = ('succeeded', 'partially_succeeded')


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _job_applies_to_cluster(job: JobExecution, cluster_id: str | None) -> bool:
    if not cluster_id:
        return True
    payload = job.payload_json or {}
    if str(payload.get('scope') or '') == 'all_clusters':
        return True
    return str(cluster_id) in {
        str(target.get('cluster_id'))
        for target in payload.get('targets') or []
        if isinstance(target, dict)
    }


def _first_relevant(jobs: list[JobExecution], cluster_id: str | None) -> JobExecution | None:
    return next((job for job in jobs if _job_applies_to_cluster(job, cluster_id)), None)


def build_tls_sync_state(*, cluster_id: str | None = None) -> dict[str, Any]:
    policy = get_or_create_job_policy('governance.tls_certificates.sync')
    base_query = JobExecution.query.filter(
        JobExecution.job_type == TLS_SYNC_JOB_TYPE,
        JobExecution.operation == TLS_SYNC_OPERATION,
    )
    active_job = _first_relevant(
        base_query.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .all(),
        cluster_id,
    )
    recent_jobs = (
        base_query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(100).all()
    )
    latest_job = _first_relevant(recent_jobs, cluster_id)
    latest_success = _first_relevant(
        [job for job in recent_jobs if job.status in _SUCCESS_STATUSES],
        cluster_id,
    )

    collected_query = TLSCertificateInventory.query
    if cluster_id:
        collected_query = collected_query.filter(TLSCertificateInventory.cluster_id == cluster_id)
    latest_collected_at = (
        collected_query.with_entities(TLSCertificateInventory.collected_at)
        .order_by(TLSCertificateInventory.collected_at.desc())
        .limit(1)
        .scalar()
    )

    last_success_at = _as_utc(latest_success.completed_at if latest_success else None)
    latest_collected_at = _as_utc(latest_collected_at)
    freshness_source = max(
        (value for value in (last_success_at, latest_collected_at) if value is not None),
        default=None,
    )
    interval_minutes = max(int(policy.interval_minutes or 360), 1)
    stale_after = timedelta(minutes=interval_minutes + min(max(interval_minutes // 4, 15), 180))
    is_stale = freshness_source is not None and datetime.now(UTC) - freshness_source > stale_after

    if active_job is not None and active_job.status == 'queued':
        label, tone, icon = 'Queued', 'pending', 'clock-3'
        helper = active_job.progress_message or 'Waiting for the inventory worker to start TLS certificate collection.'
    elif active_job is not None:
        label, tone, icon = 'Syncing', 'pending', 'loader-circle'
        helper = active_job.progress_message or 'TLS certificate collection is running in the inventory worker.'
    elif latest_job is not None and latest_job.status == 'failed':
        label, tone, icon = 'Sync Failed', 'critical', 'circle-x'
        helper = 'The most recent TLS collection failed. Review Jobs & Executions before retrying.'
    elif freshness_source is None:
        label, tone, icon = 'Not Collected', 'warning', 'clock-alert'
        helper = 'Run the first TLS sync to establish certificate inventory freshness.'
    elif is_stale:
        label, tone, icon = 'Stale', 'warning', 'clock-alert'
        helper = 'TLS inventory is older than the configured automatic synchronization window.'
    else:
        label, tone, icon = 'Current', 'normal', 'circle-check'
        helper = 'TLS certificate inventory is within the configured synchronization window.'

    progress_percent = 0
    if active_job is not None and active_job.progress_total:
        progress_percent = min(int((active_job.progress_current / active_job.progress_total) * 100), 100)

    return {
        'label': label,
        'tone': tone,
        'icon': icon,
        'helper': helper,
        'is_active': active_job is not None,
        'progress_percent': progress_percent,
        'progress_message': active_job.progress_message if active_job is not None else None,
        'active_job_public_id': active_job.public_id if active_job is not None else None,
        'last_success_at': freshness_source,
        'last_success_label': present_user_datetime(freshness_source, empty='Never'),
        'automatic_enabled': bool(policy.enabled),
        'interval_minutes': interval_minutes,
        'interval_label': (
            f'{interval_minutes // 60} Hours'
            if interval_minutes % 60 == 0
            else f'{interval_minutes} Minutes'
        ),
        'next_run_at': policy.next_run_at,
        'next_run_label': present_user_datetime(policy.next_run_at, empty='Not Scheduled'),
        'latest_job_status': latest_job.status if latest_job is not None else None,
    }

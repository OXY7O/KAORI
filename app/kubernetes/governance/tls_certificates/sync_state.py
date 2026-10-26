from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, cast, func, or_
from sqlalchemy.dialects.postgresql import JSONB

from app.common.presentation import present_user_datetime
from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.governance import TLSCertificateCollectionState, TLSCertificateInventory
from app.models.job import JobExecution
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.policies.service import get_or_create_job_policy

from .constants import TLS_COLLECTION_COLLECTED, TLS_SYNC_JOB_TYPE, TLS_SYNC_OPERATION


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _job_applies_to_cluster(job: JobExecution, cluster_id: str | None) -> bool:
    if not cluster_id:
        return True
    payload = job.payload_json or {}
    if not isinstance(payload, dict):
        return False
    return any(
        isinstance(target, dict) and str(target.get('cluster_id') or '') == str(cluster_id)
        for target in payload.get('targets') or []
    )


def _cluster_job_scope(cluster_id: str):
    """Filter target membership in PostgreSQL before ordering/limiting jobs.

    Fleet/subset work uses shared scope keys; those keys alone are not proof
    a selected cluster was an actual job target. Canonical payload targets
    are explicit and JSONB containment works on PostgreSQL's JSON column.
    """
    return cast(JobExecution.payload_json, JSONB).contains({'targets': [{'cluster_id': str(cluster_id)}]})


def _last_successful_cluster_job(base_query, cluster_id: str) -> JobExecution | None:
    """Find one source-qualified success without a global 100-job cutoff."""
    failed_target = cast(JobExecution.result_summary_json, JSONB).contains(
        {'failures': [{'cluster_id': str(cluster_id)}]}
    )
    return (
        base_query.filter(_cluster_job_scope(cluster_id))
        .filter(JobExecution.completed_at.is_not(None))
        .filter(
            or_(
                JobExecution.status == 'succeeded',
                and_(
                    JobExecution.status == 'partially_succeeded',
                    JobExecution.result_summary_json.is_not(None),
                    ~failed_target,
                ),
            )
        )
        .order_by(JobExecution.completed_at.desc(), JobExecution.id.desc())
        .first()
    )


def _first_relevant(jobs: list[JobExecution], cluster_id: str | None) -> JobExecution | None:
    return next((job for job in jobs if _job_applies_to_cluster(job, cluster_id)), None)


def _successful_job_evidence_times(
    jobs: list[JobExecution],
    cluster_ids: list[str],
) -> dict[str, datetime]:
    """Bounded fallback for completed successful zero-certificate collections.

    Job result failures are cluster-specific; a partially successful fleet
    job must never qualify a failed target as successfully collected.
    """
    scoped = set(cluster_ids)
    evidence: dict[str, datetime] = {}
    for job in jobs:
        completed = _as_utc(job.completed_at)
        if job.status not in {'succeeded', 'partially_succeeded'} or completed is None:
            continue
        payload = job.payload_json or {}
        summary = job.result_summary_json or {}
        if not isinstance(payload, dict) or not isinstance(summary, dict):
            continue
        failed = {
            str(item.get('cluster_id'))
            for item in summary.get('failures') or []
            if isinstance(item, dict) and item.get('cluster_id')
        }
        for target in payload.get('targets') or []:
            if not isinstance(target, dict):
                continue
            cid = str(target.get('cluster_id') or '')
            if cid in scoped and cid not in failed:
                previous = evidence.get(cid)
                if previous is None or completed > previous:
                    evidence[cid] = completed
    return evidence


def tls_sync_stale_after(interval_minutes: int | None) -> timedelta:
    """Match the TLS sync posture evidence window for mutation admission."""
    minutes = max(int(interval_minutes or 360), 1)
    return timedelta(minutes=minutes + min(max(minutes // 4, 15), 180))


def tls_sync_evidence_is_current(observed_at: datetime | None, *, stale_after: timedelta, now: datetime) -> bool:
    """Missing, future, or aged committed evidence cannot authorize rotation."""
    at = _as_utc(observed_at)
    checked_at = _as_utc(now)
    return at is not None and checked_at is not None and at <= checked_at and checked_at - at <= stale_after


def _collection_freshness(
    *,
    cluster_ids: list[str],
    states: dict[str, TLSCertificateCollectionState],
    record_times: dict[str, datetime],
    job_success_times: dict[str, datetime] | None = None,
    stale_after: timedelta,
    now: datetime,
) -> tuple[datetime | None, bool, bool]:
    """Derive freshness only from committed successful source evidence.

    Certificate record timestamps remain last-known-good on a failed refresh.
    A collection-state timestamp is eligible only while its Secret source
    explicitly reports Collected; updated_at records attempt time, not success.
    """
    candidates: list[datetime] = []
    stale = False
    exceptions = False
    for cluster_id in cluster_ids:
        state = states.get(cluster_id)
        record_time = _as_utc(record_times.get(cluster_id))
        secret_ok = state is not None and state.secret_collection_status == TLS_COLLECTION_COLLECTED
        ingress_ok = state is not None and state.ingress_mapping_status == TLS_COLLECTION_COLLECTED
        state_time = _as_utc(state.collected_at) if secret_ok and state is not None else None
        source_time = max((t for t in (record_time, state_time) if t is not None), default=None)
        if source_time is None:
            # Only use job evidence when there is no certificate row or currently
            # admitted success timestamp (e.g. a successfully scanned empty scope).
            source_time = _as_utc((job_success_times or {}).get(cluster_id))
        if source_time is not None:
            candidates.append(source_time)
        if source_time is None or now - source_time > stale_after:
            stale = True
        if not secret_ok or not ingress_ok:
            exceptions = True
    return max(candidates, default=None), stale, exceptions


def build_tls_sync_state(*, cluster_id: str | None = None) -> dict[str, Any]:
    policy = get_or_create_job_policy('governance.tls_certificates.sync')
    base_query = JobExecution.query.filter(
        JobExecution.job_type == TLS_SYNC_JOB_TYPE,
        JobExecution.operation == TLS_SYNC_OPERATION,
    )
    scoped_query = base_query.filter(_cluster_job_scope(cluster_id)) if cluster_id else base_query
    active_job = (
        scoped_query.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent_jobs = scoped_query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(100).all()
    latest_job = _first_relevant(recent_jobs, cluster_id)
    interval_minutes = max(int(policy.interval_minutes or 360), 1)
    stale_after = tls_sync_stale_after(interval_minutes)
    scoped_ids = [str(cluster_id)] if cluster_id else [str(row[0]) for row in db.session.query(Cluster.id).all()]
    states = (
        {
            str(state.cluster_id): state
            for state in TLSCertificateCollectionState.query.filter(
                TLSCertificateCollectionState.cluster_id.in_(scoped_ids)
            ).all()
        }
        if scoped_ids
        else {}
    )
    record_times = (
        {
            str(cid): collected
            for cid, collected in db.session.query(
                TLSCertificateInventory.cluster_id,
                func.max(TLSCertificateInventory.collected_at),
            )
            .filter(TLSCertificateInventory.cluster_id.in_(scoped_ids))
            .group_by(TLSCertificateInventory.cluster_id)
            .all()
        }
        if scoped_ids
        else {}
    )
    job_success_times = _successful_job_evidence_times(recent_jobs, scoped_ids)
    # Successful zero-certificate scans must not vanish behind unrelated
    # cluster jobs (or 100 newer target failures). Only probe clusters with
    # no usable row/state success clock; each query returns at most one job.
    for cid in scoped_ids:
        state = states.get(cid)
        if cid in record_times or (
            state is not None
            and state.secret_collection_status == TLS_COLLECTION_COLLECTED
            and state.collected_at is not None
        ):
            continue
        verified = _last_successful_cluster_job(base_query, cid)
        if verified is not None:
            job_success_times.update(_successful_job_evidence_times([verified], [cid]))

    freshness_source, is_stale, collection_exceptions = _collection_freshness(
        cluster_ids=scoped_ids,
        states=states,
        record_times=record_times,
        job_success_times=job_success_times,
        stale_after=stale_after,
        now=datetime.now(UTC),
    )

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
    elif collection_exceptions:
        label, tone, icon = 'Collection Exceptions', 'warning', 'shield-alert'
        helper = 'One or more TLS Secret or Ingress evidence sources are unavailable or incomplete.'
    elif is_stale:
        label, tone, icon = 'Stale', 'warning', 'clock-alert'
        helper = 'TLS inventory is older than the configured automatic synchronization window.'
    else:
        label, tone, icon = 'Current', 'normal', 'circle-check'
        helper = 'TLS certificate inventory is within the configured synchronization window.'

    progress_current = max(int(active_job.progress_current or 0), 0) if active_job is not None else 0
    progress_total = max(int(active_job.progress_total or 0), 0) if active_job is not None else 0
    progress_percent = 0
    if progress_total:
        progress_percent = max(
            0,
            min(round((progress_current / progress_total) * 100), 100),
        )

    return {
        'label': label,
        'tone': tone,
        'icon': icon,
        'helper': helper,
        'is_active': active_job is not None,
        'progress_current': progress_current,
        'progress_total': progress_total,
        'progress_percent': progress_percent,
        'progress_message': active_job.progress_message if active_job is not None else None,
        'active_job_public_id': active_job.public_id if active_job is not None else None,
        'last_success_at': freshness_source,
        'last_success_label': present_user_datetime(freshness_source, empty='Never'),
        'automatic_enabled': bool(policy.enabled),
        'interval_minutes': interval_minutes,
        'interval_label': (
            f'{interval_minutes // 60} Hours' if interval_minutes % 60 == 0 else f'{interval_minutes} Minutes'
        ),
        'next_run_at': policy.next_run_at,
        'next_run_label': present_user_datetime(policy.next_run_at, empty='Not Scheduled'),
        'latest_job_status': latest_job.status if latest_job is not None else None,
    }

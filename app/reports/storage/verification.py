from __future__ import annotations

from typing import Any

from flask import current_app
from sqlalchemy import select

from app.extensions.db import db
from app.models.job import JobExecution
from app.reports.storage.state import get_shared_report_storage_status, get_storage_config_fingerprint


def worker_managed_storage_readiness_enabled() -> bool:
    """Return whether S3 readiness is owned by the shared worker monitor."""

    return bool(
        current_app.config.get('REPORT_STORAGE_HEALTH_MONITOR_ENABLED', True)
        and str(current_app.config.get('REDIS_URL') or '').strip()
    )


def get_stale_shared_storage_status(backend_name: str) -> dict[str, Any] | None:
    if backend_name != 's3':
        return None
    return get_shared_report_storage_status(backend_name, allow_stale=True)


def request_readiness_fallback(
    backend_name: str,
    previous_shared_status: dict[str, Any] | None,
    *,
    force: bool,
) -> dict[str, Any] | None:
    if backend_name != 's3' or force or not worker_managed_storage_readiness_enabled():
        return None
    return worker_managed_storage_readiness_fallback(backend_name, previous_shared_status)


def worker_managed_storage_readiness_fallback(
    backend_name: str,
    previous_shared_status: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fail closed without performing provider I/O from a web request."""

    if previous_shared_status is not None:
        return {
            **previous_shared_status,
            'backend': backend_name,
            'available': False,
            'write_available': False,
            'state': 'stale',
            'status': 'Refresh Pending',
            'tone': 'amber',
            'icon': 'loader-circle',
            'title': 'Storage Readiness Is Awaiting Worker Refresh',
            'description': (
                'The last shared storage observation is stale. KAORI is waiting for the background storage monitor; '
                'web requests do not probe S3 or MinIO directly.'
            ),
            'action_label': 'Verify Storage',
            'source': 'periodic_stale',
            'stale': True,
        }

    return {
        'backend': backend_name,
        'label': 'S3-compatible storage' if backend_name == 's3' else 'Report storage',
        'configured': True,
        'reachable': False,
        'available': False,
        'read_available': False,
        'write_available': False,
        'write_verification_required': False,
        'state': 'pending',
        'status': 'Checking',
        'tone': 'amber',
        'icon': 'loader-circle',
        'title': 'Storage Readiness Is Awaiting Worker Check',
        'description': (
            'KAORI has not received a fresh shared readiness observation yet. The background storage worker owns '
            'S3 and MinIO connectivity checks so web requests remain responsive.'
        ),
        'action_label': 'Verify Storage',
        'source': 'worker_pending',
        'stale': True,
        'age_seconds': 0,
        'stale_after_seconds': 0,
    }


def _verification_job_rows(backend_name: str) -> list[JobExecution]:
    statement = (
        select(JobExecution)
        .where(
            JobExecution.job_type == 'report_storage',
            JobExecution.operation == 'verify_backend',
            JobExecution.scope_type == 'report_storage_backend',
            JobExecution.scope_key == backend_name,
        )
        .order_by(JobExecution.created_at.desc())
        .limit(20)
    )
    return list(db.session.scalars(statement).all())


def _verification_timestamp_label(job: JobExecution | None) -> str:
    if job is None:
        return 'Not checked'
    value = job.completed_at or job.heartbeat_at or job.started_at or job.queued_at
    if value is None:
        return 'Not checked'
    return value.strftime('%d %b %Y %H:%M UTC')


def get_report_storage_verification_presentation(backend_name: str | None = None) -> dict[str, Any]:
    """Present canonical strong-verification state without provider exceptions."""

    normalized_backend = str(
        backend_name or current_app.config.get('REPORT_STORAGE_BACKEND', 'local') or 'local'
    ).lower().strip()
    fingerprint = get_storage_config_fingerprint(normalized_backend)
    jobs = [
        job
        for job in _verification_job_rows(normalized_backend)
        if str((job.payload_json or {}).get('config_fingerprint') or '') == fingerprint
    ]
    latest = jobs[0] if jobs else None
    last_success = next((job for job in jobs if job.status in {'succeeded', 'partially_succeeded'}), None)

    if latest is None:
        return {
            'state': 'never_checked',
            'status': 'Never Checked',
            'tone': 'unknown',
            'icon': 'circle-dashed',
            'title': 'Strong Verification Not Run',
            'description': 'Run Verify Storage to validate the write, confirm, and cleanup path from the worker.',
            'detail': 'No strong verification execution exists for the current storage configuration.',
            'is_active': False,
            'job_execution_id': None,
            'job_public_id': None,
            'checked_label': 'Not checked',
            'last_success_label': 'No successful verification recorded',
        }

    evidence = dict((latest.payload_json or {}).get('verification_evidence') or {})
    status_map: dict[str, tuple[str, str, str, str, str]] = {
        'queued': (
            'queued',
            'Queued',
            'info',
            'clock-3',
            'Strong verification is waiting for the report-storage worker.',
        ),
        'running': (
            'running',
            'Verifying',
            'info',
            'loader-circle',
            'The worker is validating the storage write, confirm, and cleanup path.',
        ),
        'retrying': (
            'retrying',
            'Verifying',
            'warning',
            'rotate-cw',
            'The worker is retrying strong storage verification.',
        ),
        'succeeded': (
            'healthy',
            'Healthy',
            'normal',
            'circle-check',
            'Strong backend verification completed successfully.',
        ),
        'partially_succeeded': (
            'healthy',
            'Healthy',
            'normal',
            'circle-check',
            'Strong backend verification completed successfully.',
        ),
        'failed': (
            'failed',
            'Failed',
            'critical',
            'circle-x',
            'Strong backend verification did not complete successfully.',
        ),
        'canceled': (
            'canceled',
            'Canceled',
            'warning',
            'circle-slash',
            'Strong backend verification was canceled before completion.',
        ),
        'expired': (
            'failed',
            'Failed',
            'critical',
            'clock-alert',
            'Strong backend verification expired before completion.',
        ),
    }
    state, label, tone, icon, description = status_map.get(
        latest.status,
        (
            'pending',
            latest.status.replace('_', ' ').title(),
            'unknown',
            'circle-dashed',
            'Verification state is pending.',
        ),
    )
    detail = str(evidence.get('detail') or '')
    if latest.status == 'failed' and not detail:
        detail = 'Review the report-storage worker log for provider-level technical evidence.'

    return {
        'state': state,
        'status': label,
        'tone': tone,
        'icon': icon,
        'title': (
            str(evidence.get('title') or 'Report Storage Verification Failed')
            if latest.status == 'failed'
            else f'Report Storage Verification {label}'
        ),
        'description': description,
        'detail': detail,
        'failure_class': evidence.get('failure_class'),
        'is_active': bool(latest.is_active),
        'job_execution_id': latest.id,
        'job_public_id': latest.public_id,
        'checked_label': _verification_timestamp_label(latest),
        'last_success_label': (
            f'Last successful verification: {_verification_timestamp_label(last_success)}'
            if last_success is not None
            else 'No successful verification recorded'
        ),
    }

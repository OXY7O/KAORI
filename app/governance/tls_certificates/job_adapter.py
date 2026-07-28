from __future__ import annotations

from typing import Any

from app.governance.tls_certificates.sync_jobs import (
    NoEligibleTLSCertificateTargets,
    TLS_SYNC_JOB_TYPE,
    TLS_SYNC_OPERATION,
    build_tls_certificate_targets,
    enqueue_tls_certificate_sync,
)
from app.jobs.constants import ACTIVE_JOB_STATUSES
from app.jobs.definitions.base import RegisteredJobDispatchResult
from app.jobs.policies.presentation import present_interval
from app.jobs.presentation import present_job_execution
from app.models.governance import TLSCertificateInventory
from app.models.job import JobExecution, JobPolicy


def _present_job(job: JobExecution | None) -> dict[str, Any] | None:
    return present_job_execution(job) if job is not None else None


def dispatch_tls_certificate_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    cluster_id = str((parameters or {}).get('cluster_id') or '').strip() or None
    try:
        job, created = enqueue_tls_certificate_sync(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
            cluster_id=cluster_id,
        )
    except NoEligibleTLSCertificateTargets as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'TLS certificate synchronization was queued in the inventory worker.'
            if created
            else 'The request joined an active TLS certificate synchronization.'
        ),
        job=job,
        created=created,
    )


def build_tls_certificate_sync_context(policy: JobPolicy) -> dict[str, Any]:
    targets = build_tls_certificate_targets()
    jobs = JobExecution.query.filter(
        JobExecution.job_type == TLS_SYNC_JOB_TYPE,
        JobExecution.operation == TLS_SYNC_OPERATION,
    )
    active_job = (
        jobs.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        )
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent_jobs = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    latest_job = recent_jobs[0] if recent_jobs else None

    if active_job is not None:
        configuration_state = {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
        }
    elif not targets:
        configuration_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
        }
    elif policy.enabled:
        configuration_state = {
            'label': 'Enabled',
            'tone': 'normal',
            'icon': 'circle-check',
        }
    else:
        configuration_state = {
            'label': 'Manual Only',
            'tone': 'unknown',
            'icon': 'mouse-pointer-click',
        }

    if active_job is not None:
        execution_state = {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
            'description': 'A TLS certificate sync is active.',
        }
    elif targets:
        execution_state = {
            'label': 'Ready',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'Eligible clusters are ready to sync.',
        }
    else:
        execution_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
            'description': 'Enable a Kubernetes binding before syncing TLS inventory.',
        }

    return {
        'eligible_cluster_count': len(targets),
        'tracked_secret_count': TLSCertificateInventory.query.count(),
        'interval_label': present_interval(policy.interval_minutes),
        'configuration_state': configuration_state,
        'execution_state': execution_state,
        'active_job': _present_job(active_job),
        'latest_job': _present_job(latest_job),
        'recent_jobs': [_present_job(job) for job in recent_jobs],
    }

"""KAORI registered Jobs adapter for Source Control repository inventory (#2742)."""

from __future__ import annotations

from typing import Any

from app.common.job_execution_presentation import present_job_execution
from app.integrations.source_control.sync_jobs import (
    NoEligibleSourceControlTargets,
    build_source_repository_targets,
    enqueue_source_repository_sync,
)
from app.models.job import JobExecution, JobPolicy
from app.models.source_control import SourceInstallation
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.policies.presentation import present_interval


def dispatch_source_repositories(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    raw = (parameters or {}).get('installation_record_id')
    installation_id: int | None = None
    if raw is not None:
        if isinstance(raw, bool) or not str(raw).isascii() or not str(raw).isdecimal():
            return RegisteredJobDispatchResult(
                status='blocked', message='Invalid Source Control installation scope.',
            )
        installation_id = int(raw)
        if installation_id <= 0:
            return RegisteredJobDispatchResult(
                status='blocked', message='Invalid Source Control installation scope.',
            )
    try:
        job, created = enqueue_source_repository_sync(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
            installation_record_id=installation_id,
        )
    except NoEligibleSourceControlTargets as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'Source Control repository reconciliation was queued.'
            if created else 'Joined an active Source Control repository reconciliation.'
        ),
        job=job, created=created,
    )


def build_source_repositories_context(policy: JobPolicy) -> dict[str, Any]:
    """Use shared Jobs UX: unknown evidence stays unknown until an admitted scan."""
    registered = SourceInstallation.query.count()
    try:
        targets = build_source_repository_targets()
        eligible = len(targets)
    except NoEligibleSourceControlTargets:
        eligible = 0
    job_query = JobExecution.query.filter_by(
        job_type='source_control_repository_inventory',
        operation='sync_source_control_repositories',
    )
    recent = job_query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    active = (
        job_query.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        ).order_by(JobExecution.updated_at.desc(), JobExecution.id.desc()).first()
    )
    status = {
        'label': 'Execution Active' if active else ('Ready' if eligible else 'Blocked'),
        'tone': 'pending' if active else ('normal' if eligible else 'warning'),
        'icon': 'loader-circle' if active else ('circle-check' if eligible else 'shield-alert'),
        'description': (
            'Canonical inventory worker is reconciling eligible GitHub installation grants.'
            if active else (
                'GitHub installations are admitted and eligible.'
                if eligible else 'No admitted and validated GitHub App installation is available.'
            )
        ),
    }
    return {
        'registered_system_count': registered,
        'eligible_system_count': eligible,
        'eligible_target_count': eligible,
        'blocked_system_count': max(registered - eligible, 0),
        'interval_label': present_interval(policy.interval_minutes),
        'latest_job': present_job_execution(recent[0]) if recent else None,
        'recent_jobs': [present_job_execution(j) for j in recent],
        'active_job': present_job_execution(active) if active else None,
        'execution_state': status,
        'readiness_state': {
            'label': 'Sync Eligible' if eligible else 'Blocked',
            'tone': 'normal' if eligible else 'warning',
            'icon': 'link-2' if eligible else 'shield-alert',
            'description': status['description'],
        },
        'configuration_state': {
            'label': 'Execution Active' if active else ('Enabled' if policy.enabled else 'Manual Only'),
            'tone': 'pending' if active else ('normal' if policy.enabled else 'unknown'),
            'icon': 'loader-circle' if active else ('circle-check' if policy.enabled else 'mouse-pointer-click'),
        },
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled else 'disabled',
            'icon': 'circle-check' if policy.enabled else 'circle-pause',
            'description': 'Provider-gated metadata-only repository reconciliation.',
        },
    }

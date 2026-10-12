from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from flask import abort, url_for
from sqlalchemy import or_

from app.common.job_execution_contract import job_operation_label
from app.common.pagination import normalize_per_page, paginate_query
from app.models.audit import AuditEvent
from app.models.job import JobExecution
from app.platform_operations.notifications.metadata import redact_operational_text

# These prefixes are concrete current AuditEvent producers, not a generic
# unreviewed administrative-audit SQL union.
_SCOPES = {
    'automatic-jobs': {
        'label': 'Automatic Jobs',
        'source': 'Job Administration',
        'prefix': 'automatic_job_',
        'target_types': ('job_execution',),
    },
    'tenant-sync': {
        'label': 'Tenant Inventory Sync',
        'source': 'Tenant Governance',
        'prefix': 'kubernetes_tenant_inventory_sync_',
        'target_types': ('job_execution', 'kubernetes_tenant_inventory'),
    },
}

_OUTCOMES = (
    ('all', 'All Outcomes'),
    ('succeeded', 'Succeeded'),
    ('partially_succeeded', 'Partially Succeeded'),
    ('failed', 'Failed'),
    ('queued', 'Queued'),
    ('canceled', 'Canceled'),
)
_TIME_RANGES = (
    ('all', 'All Hot Records'),
    ('24h', '24 Hours'),
    ('7d', '7 Days'),
    ('30d', '30 Days'),
    ('90d', '90 Days'),
)
_TIME_DELTA = {
    '24h': timedelta(hours=24),
    '7d': timedelta(days=7),
    '30d': timedelta(days=30),
    '90d': timedelta(days=90),
}


def _available_scopes(*, can_view_jobs: bool, can_manage_tenants: bool) -> tuple[str, ...]:
    result: list[str] = []
    if can_view_jobs:
        result.append('automatic-jobs')
    if can_manage_tenants:
        result.append('tenant-sync')
    return tuple(result)


def build_administrative_evidence_context(
    *,
    scope: str | None,
    page: int,
    per_page: int = 5,
    search: str = '',
    outcome: str = 'all',
    time_range: str = 'all',
    can_view_jobs: bool,
    can_manage_tenants: bool,
    can_browse_job_archives: bool = False,
) -> dict[str, Any] | None:
    """Browse explicit administrative AuditEvent sources without copying evidence."""
    available = _available_scopes(
        can_view_jobs=can_view_jobs, can_manage_tenants=can_manage_tenants
    )
    if not available:
        return None
    selected = (scope or '').strip() or available[0]
    if selected not in available:
        abort(403)
    specification = _SCOPES[selected]
    normalized_search = str(search or '').strip()[:120]
    normalized_outcome = outcome if outcome in dict(_OUTCOMES) else 'all'
    normalized_time_range = time_range if time_range in dict(_TIME_RANGES) else 'all'
    normalized_per_page = normalize_per_page(per_page)
    query = (
        AuditEvent.query.filter(
            AuditEvent.target_type.in_(specification['target_types']),
            AuditEvent.action.startswith(specification['prefix'], autoescape=True),
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    )
    if normalized_search:
        query = query.filter(
            or_(
                AuditEvent.action.icontains(normalized_search, autoescape=True),
                AuditEvent.summary.icontains(normalized_search, autoescape=True),
                AuditEvent.target_id.icontains(normalized_search, autoescape=True),
            )
        )
    if normalized_outcome != 'all':
        query = query.filter(
            AuditEvent.action.endswith(f'_{normalized_outcome}', autoescape=True)
        )
        if normalized_outcome == 'succeeded':
            query = query.filter(
                ~AuditEvent.action.endswith('_partially_succeeded', autoescape=True)
            )
    if normalized_time_range != 'all':
        query = query.filter(
            AuditEvent.created_at >= datetime.now(UTC) - _TIME_DELTA[normalized_time_range]
        )
    events, pagination = paginate_query(query, page=page, per_page=normalized_per_page)
    # One permission-scoped lookup across the visible AuditEvent page.
    job_ids = {
        str(event.target_id)
        for event in events
        if event.target_type == 'job_execution' and event.target_id
    }
    hot_jobs = (
        {job.public_id: job for job in JobExecution.query.filter(JobExecution.public_id.in_(job_ids)).all()}
        if can_view_jobs and job_ids
        else {}
    )
    rows: list[dict[str, Any]] = []
    for event in events:
        action_suffix = event.action.removeprefix(specification['prefix'])
        outcome_key = (
            'partially_succeeded'
            if action_suffix.endswith('partially_succeeded')
            else action_suffix.rsplit('_', 1)[-1]
        )
        status_tone = {
            'succeeded': 'success',
            'failed': 'error',
            'partially_succeeded': 'warning',
            'canceled': 'warning',
            'queued': 'info',
        }.get(outcome_key, 'info')
        # The administrative model has only a nullable actor FK, never a
        # committed identity/role/auth-source snapshot: do not reconstruct it.
        job_url = None
        archive_history_url = None
        # Missing from hot storage does not prove a verified cold archive contains this job.
        job_unavailable = bool(
            can_view_jobs and event.target_type == 'job_execution' and event.target_id
        )
        # The AuditEvent action alone does not identify the actual job operation.
        display_action = f"{specification['label']} · {action_suffix.replace('_', ' ').title()}"
        if job_unavailable:
            job = hot_jobs.get(str(event.target_id))
            if job is not None:
                display_action = redact_operational_text(
                    job_operation_label(job.operation), limit=120
                ) or display_action
                job_url = url_for('jobs.executions', execution_tab='registry', search=job.public_id)
                job_unavailable = False
            elif can_browse_job_archives:
                archive_history_url = url_for(
                    'platform_operations.data_lifecycle.index',
                    tab='history',
                    archive_domain='job_execution',
                )
        rows.append({
            'id': event.id,
            'action': redact_operational_text(event.action, limit=120),
            'display_action': display_action,
            'source_label': specification['source'],
            'status_label': outcome_key.replace('_', ' ').title(),
            'status_tone': status_tone,
            'actor_label': f'User ID #{event.actor_user_id}' if event.actor_user_id is not None else 'Not recorded',
            'actor_detail': 'Actor FK · not a snapshot' if event.actor_user_id is not None else 'No actor FK',
            'summary': redact_operational_text(event.summary, limit=255),
            'created_at': event.created_at,
            'actor_reference': (
                f'User ID #{event.actor_user_id} · FK only (not a snapshot)'
                if event.actor_user_id is not None
                else 'No human actor recorded'
            ),
            'job_url': job_url,
            'archive_history_url': archive_history_url,
            'job_unavailable': job_unavailable,
        })
    return {
        'scope': selected,
        'scope_label': specification['label'],
        'scope_options': [{'key': key, 'label': _SCOPES[key]['label']} for key in available],
        'source_label': specification['source'],
        'rows': rows,
        'pagination': pagination,
        'filters': {
            'search': normalized_search,
            'outcome': normalized_outcome,
            'time_range': normalized_time_range,
        },
        'outcome_options': _OUTCOMES,
        'time_range_options': _TIME_RANGES,
        'has_active_filters': (
            selected != available[0]
            or bool(normalized_search)
            or normalized_outcome != 'all'
            or normalized_time_range != 'all'
        ),
    }

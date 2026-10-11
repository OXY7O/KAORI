from __future__ import annotations

from typing import Any

from flask import abort, url_for

from app.common.pagination import paginate_query
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
    can_view_jobs: bool,
    can_manage_tenants: bool,
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
    query = (
        AuditEvent.query.filter(
            AuditEvent.target_type.in_(specification['target_types']),
            AuditEvent.action.startswith(specification['prefix'], autoescape=True),
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    )
    events, pagination = paginate_query(query, page=page, per_page=5)
    rows: list[dict[str, Any]] = []
    for event in events:
        action_suffix = event.action.removeprefix(specification['prefix'])
        outcome_key = action_suffix.rsplit('_', 1)[-1]
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
        if can_view_jobs and event.target_type == 'job_execution' and event.target_id:
            job = JobExecution.query.filter_by(public_id=event.target_id).first()
            if job is not None:
                job_url = url_for('jobs.executions', execution_tab='registry', search=job.public_id)
        rows.append({
            'id': event.id,
            'action': redact_operational_text(event.action, limit=120),
            'display_action': f"{specification['label']} · {action_suffix.replace('_', ' ').title()}",
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
        })
    return {
        'scope': selected,
        'scope_label': specification['label'],
        'scope_options': [{'key': key, 'label': _SCOPES[key]['label']} for key in available],
        'source_label': specification['source'],
        'rows': rows,
        'pagination': pagination,
    }

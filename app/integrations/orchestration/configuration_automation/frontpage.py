"""Committed-evidence Ansible provider workspace, no network/provider reads."""

from __future__ import annotations

from typing import Any

from app.common.pagination import paginate_query
from app.infrastructure_automation.source import OPERATION_ID, SOURCE_REPOSITORY, SOURCE_SHA
from app.models.job import JobExecution

_ALLOWED_STATUSES = frozenset({'queued', 'running', 'retrying', 'succeeded', 'failed', 'canceled', 'expired'})
_PILOT_JOB_TYPE = 'infrastructure_automation'
_PILOT_OPERATION = 'automation_localhost_host_facts'


def build_ansible_frontpage(*, status: str = '', page: int = 1, per_page: int = 5) -> dict[str, Any]:
    """Read only the existing KAORI JobExecution store; no live provider request."""
    selected = status if status in _ALLOWED_STATUSES else ''
    identity = JobExecution.query.filter_by(job_type=_PILOT_JOB_TYPE, operation=_PILOT_OPERATION)
    total = identity.count()
    completed = identity.filter(JobExecution.status == 'succeeded').count()
    active = identity.filter(JobExecution.status.in_(('queued', 'running', 'retrying'))).count()
    query = identity
    if selected:
        query = query.filter(JobExecution.status == selected)
    query = query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
    jobs, pagination = paginate_query(query, page=page, per_page=per_page)
    executions = [
        {
            'public_id': job.public_id,
            'status': job.status,
            'created_at': job.created_at,
            'completed_at': job.completed_at,
            'operation': OPERATION_ID,
            'source_sha': str((job.result_summary_json or {}).get('source_sha') or '')[:40],
            'distribution': str(((job.result_summary_json or {}).get('facts') or {}).get('ansible_distribution') or '')[
                :80
            ],
            'kernel': str(((job.result_summary_json or {}).get('facts') or {}).get('ansible_kernel') or '')[:80],
        }
        for job in jobs
    ]
    return {
        'source_repository': SOURCE_REPOSITORY,
        'source_sha': SOURCE_SHA,
        'operation_id': OPERATION_ID,
        'worker_queue': 'automation',
        'total_executions': total,
        'successful_executions': completed,
        'active_executions': active,
        'registered_targets': 0,
        'executions': executions,
        'pagination': pagination,
        'selected_status': selected,
        'statuses': sorted(_ALLOWED_STATUSES),
        'provider_readiness': 'Not Configured',
        'provider_lifecycle': 'Pilot · Not Admitted',
        'source_mode': 'Read-only · Localhost',
    }

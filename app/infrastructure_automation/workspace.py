"""Read-only Infrastructure Automation workspace from canonical KAORI state (#5157).

Normal GET never calls SSH, Ansible Runner, GitHub or Kubernetes providers.
IntegrationInstance, IntegrationBinding, Cluster, and JobExecution remain the
single owners of their respective records; no duplicate execution ledger.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.common.pagination import paginate_query
from app.extensions.db import db
from app.infrastructure_automation.kubernetes.committed_preflight import committed_kubespray_preflight
from app.infrastructure_automation.kubernetes.plan_currentness import committed_kubespray_plan_currentness
from app.infrastructure_automation.kubernetes.source_policy import committed_source_state
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.job import JobExecution

INTEGRATION_TYPE = 'configuration_automation'
PROVIDER_KEY = 'ansible'
_HISTORY_LIMIT = 5
_BINDING_LIMIT = 5


def _bounded_query(value: str) -> str:
    return str(value or '').strip()[:80]


def _cluster_bindings(connection: IntegrationInstance) -> list[dict[str, Any]]:
    """Only canonical cluster identities explicitly bound to this connection."""
    bindings = (
        IntegrationBinding.query.filter_by(
            integration_instance_id=connection.id,
            asset_type='kubernetes_cluster',
        )
        .order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc())
        .limit(_BINDING_LIMIT)
        .all()
    )
    keys = {str(binding.asset_key) for binding in bindings}
    clusters = (
        {cluster.id: cluster for cluster in db.session.scalars(select(Cluster).where(Cluster.id.in_(keys))).all()}
        if keys
        else {}
    )
    return [
        {
            'cluster_name': clusters[str(binding.asset_key)].name
            if str(binding.asset_key) in clusters
            else 'Unresolved cluster identity',
            'cluster_id': str(binding.asset_key) if str(binding.asset_key) in clusters else None,
            'environment': clusters[str(binding.asset_key)].environment if str(binding.asset_key) in clusters else None,
            'node_count': clusters[str(binding.asset_key)].node_count if str(binding.asset_key) in clusters else None,
            'binding_enabled': bool(binding.enabled),
            'validation_status': str(binding.validation_status or 'validation_required'),
            'execution_authorized': False,
        }
        for binding in bindings
    ]


def build_automation_workspace(
    *,
    query: str = '',
    page: int = 1,
    per_page: int = 5,
    connection_id: int | None = None,
    can_jobs: bool = False,
    can_inventory: bool = False,
) -> dict[str, Any]:
    """Return a permission-scoped, server-paginated operational projection."""
    search = _bounded_query(query)
    statement = IntegrationInstance.query.filter_by(
        integration_type=INTEGRATION_TYPE,
        provider_key=PROVIDER_KEY,
    )
    connection_total = statement.count()
    if search:
        escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        statement = statement.filter(IntegrationInstance.name.ilike(f'%{escaped}%', escape='\\'))
    statement = statement.order_by(IntegrationInstance.name.asc(), IntegrationInstance.id.asc())
    connections, pagination = paginate_query(statement, page=page, per_page=per_page)

    selected = None
    if connection_id is not None:
        if type(connection_id) is not int or connection_id <= 0:
            raise ValueError('Invalid automation connection identity.')
        selected = db.session.get(IntegrationInstance, connection_id)
        if selected is None or selected.integration_type != INTEGRATION_TYPE or selected.provider_key != PROVIDER_KEY:
            raise ValueError('Automation connection is outside the permitted provider scope.')
    elif connections:
        selected = connections[0]

    details: dict[str, Any] | None = None
    if selected is not None:
        metadata = selected.metadata_json if type(selected.metadata_json) is dict else {}
        preflight = committed_kubespray_preflight(selected)
        current_plan = committed_kubespray_plan_currentness(selected, preflight=preflight)
        scoped_jobs = JobExecution.query.filter_by(
            integration_type=INTEGRATION_TYPE,
            integration_instance_id=selected.id,
        )
        jobs = (
            scoped_jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(_HISTORY_LIMIT).all()
            if can_jobs
            else []
        )
        details = {
            'connection': selected,
            'profile_key': str(metadata.get('profile_key') or ''),
            'repository': str(metadata.get('source_repository') or ''),
            'source_revision': str(metadata.get('source_sha') or ''),
            'source_state': committed_source_state(metadata),
            'preflight': preflight.presentation(),
            'plan': current_plan.presentation(),
            'jobs': jobs,
            'job_total': scoped_jobs.count() if can_jobs else None,
            'cluster_bindings': _cluster_bindings(selected) if can_inventory else [],
            'can_jobs': can_jobs,
            'can_inventory': can_inventory,
            'execution_authorized': False,
        }
    return {
        'connections': connections,
        'pagination': pagination,
        'selected_query': search,
        'selected_connection_id': selected.id if selected is not None else None,
        'total_connections': connection_total,
        'details': details,
        'can_jobs': can_jobs,
        'can_inventory': can_inventory,
        'execution_authorized': False,
    }


def automation_connection_count() -> int:
    """Canonical Operations Center overview aggregate; never asserts Run readiness."""
    return IntegrationInstance.query.filter_by(
        integration_type=INTEGRATION_TYPE,
        provider_key=PROVIDER_KEY,
    ).count()

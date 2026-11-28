"""Committed GitHub UAT runtime and validation read-model presentation.

No external GitHub calls; SQL queries remain installation-scoped, bounded and
ordered. HTTP routes retain their own RBAC/UAT privilege checks.
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from flask import request
from flask_login import current_user
from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import ColumnElement

from app.common.pagination import paginate_query
from app.integrations.runtime.presentation import runtime_history_view, runtime_observation_state_view
from app.integrations.runtime.repository import paginate_runtime_history, runtime_history_query
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.models.job import JobExecution
from app.models.runtime import IntegrationRuntimeObservation
from app.models.source_control import SourceInstallation, SourceWebhookDelivery


def _validation_job_for(canonical, *, operation: str = 'full_validation') -> dict | None:
    task_id = get_active_validation_task_id(
        integration_type='source_control',
        operation=operation,
        integration_instance_id=canonical.id,
    )
    return build_validation_snapshot(task_id) if task_id else None


def _runtime_search_pattern(value: str) -> str:
    """Literal case-insensitive SQL LIKE pattern for bounded registry search."""
    return '%' + value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


def _installation_job_predicate(*, integration_instance_id: int, installation_id: int) -> ColumnElement[bool]:
    """Match only canonical validation/refresh or exact-installation inventory jobs.

    Scope keys can be shared by unrelated job families; provider attribution
    must verify type, operation, scope kind and the canonical target identity.
    """
    return and_(
        JobExecution.integration_type == 'source_control',
        or_(
            and_(
                JobExecution.job_type == 'integration_operation',
                JobExecution.operation.in_(('full_validation', 'runtime_refresh')),
                JobExecution.scope_type == 'integration_instance',
                JobExecution.integration_instance_id == integration_instance_id,
            ),
            and_(
                JobExecution.job_type == 'source_control_repository_inventory',
                JobExecution.operation == 'sync_source_control_repositories',
                JobExecution.scope_type == 'source_control_installation',
                JobExecution.scope_key == f'installation:{installation_id}',
            ),
        ),
    )


def _runtime_context(installation: SourceInstallation) -> dict:
    """Server-filtered, installation-scoped signed webhook receipts."""
    delivery_state = request.args.get('delivery_state', '').strip()
    delivery_search = request.args.get('delivery_search', '').strip()[:80]
    delivery_event = request.args.get('delivery_event', '').strip()[:64]

    allowed_delivery = {'received', 'queued', 'processing', 'processed', 'completed', 'failed', 'ignored'}
    if delivery_state not in allowed_delivery:
        delivery_state = ''

    scoped_deliveries = SourceWebhookDelivery.query.filter_by(installation_id=installation.id)
    delivery_event_options = [
        value
        for (value,) in (
            scoped_deliveries.with_entities(SourceWebhookDelivery.event_type)
            .distinct()
            .order_by(SourceWebhookDelivery.event_type)
            .limit(50)
            .all()
        )
        if value
    ]
    if delivery_event not in delivery_event_options:
        delivery_event = ''
    delivery_query = scoped_deliveries
    if delivery_state:
        delivery_query = delivery_query.filter(SourceWebhookDelivery.processing_state == delivery_state)
    if delivery_event:
        delivery_query = delivery_query.filter(SourceWebhookDelivery.event_type == delivery_event)
    if delivery_search:
        pattern = _runtime_search_pattern(delivery_search)
        delivery_query = delivery_query.filter(
            or_(
                SourceWebhookDelivery.event_type.ilike(pattern, escape='\\'),
                SourceWebhookDelivery.action.ilike(pattern, escape='\\'),
            )
        )
    deliveries, delivery_pagination = paginate_query(
        delivery_query.order_by(SourceWebhookDelivery.received_at.desc(), SourceWebhookDelivery.id.desc()),
        page=request.args.get('delivery_page', 1, type=int),
        per_page=request.args.get('delivery_per_page', 5, type=int),
    )

    return {
        'deliveries': deliveries,
        'delivery_pagination': delivery_pagination,
        'delivery_state': delivery_state,
        'delivery_search': delivery_search,
        'delivery_event': delivery_event,
        'delivery_event_options': delivery_event_options,
        'runtime_refresh_job': _validation_job_for(installation.integration_instance, operation='runtime_refresh'),
    }


def _observation_job_public_ids(
    installation: SourceInstallation, rows: list[IntegrationRuntimeObservation]
) -> dict[int, str]:
    """Resolve only the persisted, in-scope job references for the visible history page."""
    candidates: dict[int, str] = {}
    for row in rows:
        snapshot = row.capability_snapshot or {}
        job_id = snapshot.get('job_execution_id')
        operation = snapshot.get('operation')
        if (
            isinstance(job_id, int)
            and not isinstance(job_id, bool)
            and job_id > 0
            and isinstance(operation, str)
            and operation in {'full_validation', 'runtime_refresh'}
        ):
            candidates[job_id] = operation
    if not candidates or not current_user.is_authenticated or not current_user.has_permission('jobs.view'):
        return {}
    matches = (
        JobExecution.query.with_entities(JobExecution.id, JobExecution.public_id, JobExecution.operation)
        .filter(
            _installation_job_predicate(
                integration_instance_id=installation.integration_instance_id,
                installation_id=installation.id,
            ),
            JobExecution.id.in_(candidates),
        )
        .all()
    )
    return {
        job_id: public_id
        for job_id, public_id, operation in matches
        if public_id and candidates.get(job_id) == operation
    }


class _RuntimeScope(TypedDict):
    integration_instance_id: int
    provider_key: str
    adapter_key: str


def _runtime_observation_context(installation: SourceInstallation) -> dict:
    """Read only exact-installation, immutable provider observations from KAORI."""
    canonical = installation.integration_instance
    scope: _RuntimeScope = {
        'integration_instance_id': installation.integration_instance_id,
        'provider_key': 'github',
        'adapter_key': 'github_rest_v3',
    }
    # The operation is not present on historical observations. Never derive it
    # from job timestamps or reuse Full Validation as a runtime health check.
    current = runtime_history_query('source_control', str(installation.id), **scope).filter(
        IntegrationRuntimeObservation.capability_snapshot['operation'].as_string() == 'runtime_refresh'
    )
    invalidated_at = (canonical.metadata_json or {}).get('github_runtime_invalidated_at')
    cutoff_valid = True
    if invalidated_at is not None:
        try:
            cutoff = datetime.fromisoformat(str(invalidated_at))
            if cutoff.tzinfo is None:
                raise ValueError('Runtime invalidation timestamp must include timezone.')
            current = current.filter(IntegrationRuntimeObservation.observed_at >= cutoff)
        except (TypeError, ValueError):
            cutoff_valid = False
    latest = (
        current.order_by(IntegrationRuntimeObservation.observed_at.desc(), IntegrationRuntimeObservation.id.desc())
        .first()
        if cutoff_valid and canonical.last_checked_at is not None
        else None
    )
    state = runtime_observation_state_view(
        latest,
        fallback_readiness=canonical.readiness_status or 'validation_required',
    )
    rows, pagination = paginate_runtime_history(
        'source_control',
        str(installation.id),
        page=request.values.get('page', 1, type=int) or 1,
        per_page=request.values.get('per_page', 5, type=int) or 5,
        trigger_type=request.values.get('history_trigger', ''),
        health_status=request.values.get('history_health', ''),
        readiness=request.values.get('history_readiness', ''),
        **scope,
    )
    return {
        'runtime_state': state,
        'runtime_observed': latest is not None,
        'runtime_health': state['health_status'],
        'runtime_health_label': state['health_status_label'],
        'runtime_observation_job_id': (latest.capability_snapshot or {}).get('job_execution_id') if latest else None,
        'runtime_history': runtime_history_view(
            rows, pagination=pagination, job_public_ids=_observation_job_public_ids(installation, rows)
        ),
    }

"""Committed GitHub UAT runtime and validation read-model presentation.

No external GitHub calls; SQL queries remain installation-scoped, bounded and
ordered. HTTP routes retain their own RBAC/UAT privilege checks.
"""

from __future__ import annotations

from flask import request
from sqlalchemy import or_

from app.common.pagination import paginate_query
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.models.job import JobExecution
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


def _runtime_context(installation: SourceInstallation) -> dict:
    """Server-filtered, installation-scoped committed jobs and webhook receipts."""
    job_status = request.args.get('job_status', '').strip()
    job_search = request.args.get('job_search', '').strip()[:80]
    job_queue = request.args.get('job_queue', '').strip()[:80]
    delivery_state = request.args.get('delivery_state', '').strip()
    delivery_search = request.args.get('delivery_search', '').strip()[:80]
    delivery_event = request.args.get('delivery_event', '').strip()[:64]

    allowed_jobs = {
        'queued',
        'running',
        'retrying',
        'cancel_requested',
        'succeeded',
        'partially_succeeded',
        'failed',
        'canceled',
        'expired',
    }
    allowed_delivery = {'received', 'queued', 'processing', 'processed', 'completed', 'failed', 'ignored'}
    if job_status not in allowed_jobs:
        job_status = ''
    if delivery_state not in allowed_delivery:
        delivery_state = ''

    # Both option registries are derived from the authorised installation scope,
    # never the provider or unrestricted tenant-wide JobExecution history.
    scoped_jobs = JobExecution.query.filter(
        JobExecution.integration_type == 'source_control',
        or_(
            JobExecution.integration_instance_id == installation.integration_instance_id,
            JobExecution.scope_key == f'installation:{installation.id}',
        ),
    )
    job_queue_options = [
        value
        for (value,) in (
            scoped_jobs.with_entities(JobExecution.queue_name)
            .distinct()
            .order_by(JobExecution.queue_name)
            .limit(50)
            .all()
        )
        if value
    ]
    if job_queue not in job_queue_options:
        job_queue = ''

    jobs_query = scoped_jobs
    if job_status:
        jobs_query = jobs_query.filter(JobExecution.status == job_status)
    if job_queue:
        jobs_query = jobs_query.filter(JobExecution.queue_name == job_queue)
    if job_search:
        job_search_checks = [JobExecution.operation.ilike(_runtime_search_pattern(job_search), escape='\\')]
        numeric_job_id = job_search.removeprefix('#')
        if numeric_job_id.isascii() and numeric_job_id.isdecimal() and len(numeric_job_id) <= 18:
            job_search_checks.append(JobExecution.id == int(numeric_job_id))
        jobs_query = jobs_query.filter(or_(*job_search_checks))
    jobs, job_pagination = paginate_query(
        jobs_query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()),
        page=request.args.get('job_page', 1, type=int),
        per_page=request.args.get('job_per_page', 5, type=int),
    )

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

    last_refresh = (
        JobExecution.query.filter_by(
            integration_type='source_control',
            integration_instance_id=installation.integration_instance_id,
            operation='runtime_refresh',
        )
        .order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
        .first()
    )
    return {
        'jobs': jobs,
        'job_pagination': job_pagination,
        'job_status': job_status,
        'job_search': job_search,
        'job_queue': job_queue,
        'job_queue_options': job_queue_options,
        'deliveries': deliveries,
        'delivery_pagination': delivery_pagination,
        'delivery_state': delivery_state,
        'delivery_search': delivery_search,
        'delivery_event': delivery_event,
        'delivery_event_options': delivery_event_options,
        'last_runtime_refresh': last_refresh,
        'runtime_refresh_job': _validation_job_for(installation.integration_instance, operation='runtime_refresh'),
    }

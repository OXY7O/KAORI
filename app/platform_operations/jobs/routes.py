from __future__ import annotations

import logging
from importlib import import_module

from celery.exceptions import CeleryError
from flask import (
    Blueprint,
    abort,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.common.job_execution_contract import SYNC_ALL_INVENTORY_ACTION, job_operation_label
from app.common.job_execution_presentation import present_job_execution_detail
from app.extensions.db import db
from app.models.job import JobExecution
from app.platform_operations.jobs.configuration import (
    build_job_configuration_context,
    build_job_configuration_live_context,
    build_job_configuration_summary_context,
)
from app.platform_operations.jobs.definitions.base import JobDefinition
from app.platform_operations.jobs.dispatcher import dispatch_registered_job
from app.platform_operations.jobs.policies.forms import JobPolicyForm, ManualJobRunForm
from app.platform_operations.jobs.policies.service import update_job_policy
from app.platform_operations.jobs.presentation import build_job_execution_context, build_job_execution_status_context
from app.platform_operations.jobs.registry import get_job_definition
from app.platform_operations.jobs.service import JobCancellationNotAllowed, JobQuotaExceeded, cancel_job_execution
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)

bp = Blueprint('jobs', __name__, url_prefix='/jobs')
logger = logging.getLogger(__name__)


def _get_job_definition_or_404(job_key: str) -> JobDefinition:
    try:
        return get_job_definition(job_key)
    except LookupError:
        abort(404)


def _configuration_context(
    *,
    selected_job_key: str | None,
    policy_form: JobPolicyForm | None = None,
    policy_error: str | None = None,
) -> dict[str, object]:
    if selected_job_key is not None:
        _get_job_definition_or_404(selected_job_key)
    context = build_job_configuration_context(selected_job_key=selected_job_key)
    selected_job = context.get('selected_job')
    form = policy_form or JobPolicyForm()
    if policy_form is None and isinstance(selected_job, dict):
        policy = selected_job['policy']
        form.enabled.data = policy.enabled
        form.interval_minutes.data = policy.interval_minutes
        configuration = policy.configuration_json or {}
        form.analytics_time_ranges.data = list(configuration.get('time_ranges') or [])
        form.forecast_history_windows.data = list(configuration.get('history_windows') or [])
        form.freshness_minutes.data = configuration.get('freshness_minutes')
        form.stale_grace_minutes.data = configuration.get('stale_grace_minutes')
    context.update(
        {
            'policy_form': form,
            'manual_form': ManualJobRunForm(),
            'policy_error': policy_error,
        }
    )
    return context


def _page_context(
    *,
    active_section: str,
    selected_job_key: str | None = None,
    policy_form: JobPolicyForm | None = None,
    policy_error: str | None = None,
) -> dict[str, object]:
    if active_section == 'configuration':
        context = build_job_execution_status_context(tab='active')
        context.update(
            _configuration_context(
                selected_job_key=selected_job_key,
                policy_form=policy_form,
                policy_error=policy_error,
            )
        )
    else:
        context = _execution_context()
        context.update(
            build_job_configuration_summary_context(
                active_execution_count=int(context['job_stats']['active']),
            )
        )
    context['active_jobs_section'] = active_section
    return context


def _execution_context(*, tab_override: str | None = None) -> dict[str, object]:
    selected_tab = tab_override or request.args.get('execution_tab', request.args.get('tab', 'active')).strip()
    return build_job_execution_context(
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
        status=request.args.get('status', '').strip(),
        workload=request.args.get('workload', '').strip(),
        queue=request.args.get('queue', '').strip(),
        search=request.args.get('search', '').strip(),
        tab=selected_tab,
    )


def _configuration_live_context(job_key: str) -> dict[str, object]:
    context = build_job_configuration_live_context(selected_job_key=job_key)
    context['manual_form'] = ManualJobRunForm()
    return context


def _render_execution_fragment(context: dict[str, object], fragment: str) -> str:
    template_by_fragment = {
        'registry': 'platform_operations/jobs/executions/partials/_registry.html',
        'active': 'platform_operations/jobs/executions/partials/_active_jobs.html',
        'status': 'platform_operations/jobs/executions/partials/_status_refresh.html',
        'queues': 'platform_operations/jobs/executions/partials/_queue_activity.html',
    }
    fragment_context = dict(context)
    if fragment in {'active', 'registry', 'queues'}:
        fragment_context['embedded'] = True
    fragment_context['include_status_oob'] = fragment == 'active'
    return render_template(
        template_by_fragment.get(fragment, 'platform_operations/jobs/executions/_workspace.html'),
        **fragment_context,
    )


def _is_htmx() -> bool:
    return request.headers.get('HX-Request') == 'true'


def _render_configuration_job(
    job_key: str,
    *,
    policy_form: JobPolicyForm | None = None,
    policy_error: str | None = None,
    operation_feedback: dict[str, object] | None = None,
    status_code: int = 200,
) -> ResponseReturnValue:
    context = _configuration_context(
        selected_job_key=job_key,
        policy_form=policy_form,
        policy_error=policy_error,
    )
    context['operation_feedback'] = operation_feedback
    if operation_feedback is not None:
        context['notification_context'] = get_navigation_notification_context(user_id=int(current_user.id))
    response = make_response(
        render_template('platform_operations/jobs/configuration/_job_workspace.html', **context),
        status_code,
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


def _jobs_execution_url(*, search: str = '', queue: str = '') -> str:
    return url_for(
        'jobs.executions',
        execution_tab='registry',
        queue=queue,
        search=search,
    )


@bp.get('/')
@permission_required('jobs.view')
def index() -> ResponseReturnValue:
    return redirect(url_for('jobs.executions'))


@bp.get('/executions')
@permission_required('jobs.view')
def executions() -> ResponseReturnValue:
    if _is_htmx():
        fragment = request.args.get('fragment', 'page').strip()
        context = (
            build_job_execution_status_context(
                tab=request.args.get('execution_tab', request.args.get('tab', 'active')).strip()
            )
            if fragment == 'status'
            else _execution_context(tab_override=fragment if fragment in {'active', 'registry', 'queues'} else None)
        )
        response = make_response(_render_execution_fragment(context, fragment))
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response
    return render_template(
        'platform_operations/jobs/index.html',
        **_page_context(active_section='executions'),
    )


@bp.get('/executions/<string:public_id>/details')
@permission_required('jobs.view')
def execution_details(public_id: str) -> ResponseReturnValue:
    job = JobExecution.query.filter_by(public_id=public_id).first_or_404()
    response = make_response(
        render_template(
            'platform_operations/jobs/executions/partials/_execution_details.html',
            execution=present_job_execution_detail(job),
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


@bp.get('/configuration')
@permission_required('jobs.view')
def configuration() -> ResponseReturnValue:
    selected_job_key = request.args.get('job_key', '').strip() or None
    if _is_htmx():
        context = _configuration_context(selected_job_key=selected_job_key)
        fragment = request.args.get('fragment', 'page').strip()
        template = (
            'platform_operations/jobs/configuration/_job_workspace.html'
            if fragment == 'job'
            else 'platform_operations/jobs/configuration/_workspace.html'
        )
        response = make_response(render_template(template, **context))
        if fragment == 'job':
            response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response
    return render_template(
        'platform_operations/jobs/index.html',
        **_page_context(
            active_section='configuration',
            selected_job_key=selected_job_key,
        ),
    )


@bp.get('/configuration/<path:job_key>/status')
@permission_required('jobs.view')
def configuration_status(job_key: str) -> ResponseReturnValue:
    context = _configuration_live_context(job_key)
    response = make_response(
        render_template('platform_operations/jobs/configuration/_live_status_response.html', **context)
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


@bp.post('/configuration/<path:job_key>')
@permission_required('jobs.configure')
def update_policy(job_key: str) -> ResponseReturnValue:
    definition = _get_job_definition_or_404(job_key)
    form = JobPolicyForm()
    if not form.validate_on_submit():
        if _is_htmx():
            return _render_configuration_job(job_key, policy_form=form)
        context = _page_context(
            active_section='configuration',
            selected_job_key=job_key,
            policy_form=form,
        )
        return render_template('platform_operations/jobs/index.html', **context), 422

    try:
        configuration = dict(definition.default_configuration or {})
        if job_key == 'analytics.materialize':
            configuration.update(
                {
                    'time_ranges': list(form.analytics_time_ranges.data or ['24h', '7d', '30d', '60d']),
                    'freshness_minutes': int(form.freshness_minutes.data or 20),
                    'stale_grace_minutes': int(form.stale_grace_minutes.data or 1440),
                }
            )
        elif job_key in {'analytics.forecast.materialize', 'object_storage.forecast.materialize'}:
            configuration.update(
                {
                    'history_windows': list(form.forecast_history_windows.data or ['7d', '30d', '90d']),
                    'freshness_minutes': int(form.freshness_minutes.data or 120),
                    'stale_grace_minutes': int(form.stale_grace_minutes.data or 4320),
                }
            )
        policy = update_job_policy(
            job_key=job_key,
            enabled=bool(form.enabled.data),
            interval_minutes=int(form.interval_minutes.data or definition.default_interval_minutes),
            user_id=int(current_user.id),
            configuration=configuration,
        )
    except ValueError as exc:
        if _is_htmx():
            return _render_configuration_job(
                job_key,
                policy_form=form,
                policy_error=str(exc),
            )
        context = _page_context(
            active_section='configuration',
            selected_job_key=job_key,
            policy_form=form,
            policy_error=str(exc),
        )
        return render_template('platform_operations/jobs/index.html', **context), 422

    is_htmx = _is_htmx()
    feedback = record_operational_activity(
        user_id=int(current_user.id),
        event_type='job_policy_updated',
        status='success',
        title=f'{definition.name} Policy Updated',
        message=(
            f'Automatic execution runs every {policy.interval_minutes} minutes.'
            if policy.enabled
            else 'Automatic execution is disabled. Manual execution remains available.'
        ),
        detail='The database-backed policy is applied by the generic job scheduler without restarting Celery Beat.',
        action_url=url_for('jobs.configuration', job_key=job_key),
        action_label='Review Job Configuration',
        action_icon='sliders-horizontal',
        metadata={
            'job_key': job_key,
            'enabled': policy.enabled,
            'interval_minutes': policy.interval_minutes,
            'scope_type': policy.scope_type,
            'scope_key': policy.scope_key,
            'configuration': policy.configuration_json or {},
        },
        queue_feedback=not is_htmx,
    )
    if is_htmx:
        return _render_configuration_job(job_key, operation_feedback=feedback)
    return redirect(url_for('jobs.configuration', job_key=job_key))


def _quick_action_response(*, accepted: bool) -> ResponseReturnValue:
    if _is_htmx():
        response = make_response('', 202 if accepted else 204)
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response
    return redirect(_jobs_execution_url(queue='inventory'))


@bp.post('/quick-actions/inventory/sync-all')
@permission_required('jobs.execute')
def quick_sync_all_inventory() -> ResponseReturnValue:
    """Dispatch every inventory domain the current user is allowed to execute."""
    job_keys: list[str] = []
    if current_user.has_permission('clusters.sync'):
        job_keys.append('kubernetes.inventory.sync')
    if current_user.has_permission('storage.sync'):
        job_keys.append('object_storage.inventory.sync')
    if not job_keys:
        abort(403)

    accepted_names: list[str] = []
    active_names: list[str] = []
    blocked_messages: list[str] = []
    failed_names: list[str] = []

    for job_key in job_keys:
        definition = _get_job_definition_or_404(job_key)
        try:
            outcome = dispatch_registered_job(
                job_key=job_key,
                trigger_type='manual',
                requested_by_user_id=int(current_user.id),
            )
        except (
            CeleryError,
            JobQuotaExceeded,
            KombuOperationalError,
            OSError,
            RuntimeError,
            SQLAlchemyError,
        ):
            logger.exception('Quick Action could not dispatch registered inventory job %s.', job_key)
            failed_names.append(definition.name)
            continue

        if outcome.accepted:
            if outcome.created:
                accepted_names.append(definition.name)
            else:
                active_names.append(definition.name)
            continue
        blocked_messages.append(f'{definition.name}: {outcome.message}')

    accepted = bool(accepted_names or active_names)
    issue_count = len(blocked_messages) + len(failed_names)
    if accepted and not issue_count:
        feedback_status = 'success' if accepted_names else 'info'
        feedback_title = 'All Inventory Sync Queued' if accepted_names else 'Inventory Sync Already Active'
    elif accepted:
        feedback_status = 'warning'
        feedback_title = 'Inventory Sync Partially Queued'
    else:
        feedback_status = 'warning' if blocked_messages and not failed_names else 'error'
        feedback_title = 'Inventory Sync Could Not Start'

    queued_summary = ', '.join(accepted_names) or 'No new inventory jobs'
    active_summary = ', '.join(active_names)
    issue_summary = '; '.join([*blocked_messages, *(f'{name}: dispatch failed' for name in failed_names)])
    message_parts = [queued_summary]
    if active_summary:
        message_parts.append(f'Already active: {active_summary}')

    record_operational_activity(
        user_id=int(current_user.id),
        event_type=f'{SYNC_ALL_INVENTORY_ACTION}_quick_action',
        status=feedback_status,
        title=feedback_title,
        message='. '.join(message_parts) + '.',
        detail=issue_summary or 'Track each domain execution independently in Jobs & Executions.',
        action_url=_jobs_execution_url(queue='inventory'),
        action_label='Open Job Executions',
        action_icon='list-checks',
        metadata={
            'job_keys': job_keys,
            'queued_jobs': accepted_names,
            'active_jobs': active_names,
            'blocked_jobs': blocked_messages,
            'failed_jobs': failed_names,
            'operation': SYNC_ALL_INVENTORY_ACTION,
            'feedback_delivery': 'activity_center',
        },
        queue_feedback=True,
    )
    return _quick_action_response(accepted=accepted)


@bp.post('/configuration/<path:job_key>/run')
@permission_required('jobs.execute')
def run_now(job_key: str) -> ResponseReturnValue:
    definition = _get_job_definition_or_404(job_key)
    domain_permission = definition.domain_execute_permission
    if domain_permission and not current_user.has_permission(domain_permission):
        abort(403)
    form = ManualJobRunForm()
    is_htmx = _is_htmx()
    if not form.validate_on_submit():
        if is_htmx:
            return _render_configuration_job(job_key)
        return redirect(url_for('jobs.configuration', job_key=job_key))

    try:
        outcome = dispatch_registered_job(
            job_key=job_key,
            trigger_type='manual',
            requested_by_user_id=int(current_user.id),
        )
    except JobQuotaExceeded as exc:
        db.session.rollback()
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='job_manual_dispatch',
            status='warning',
            title=f'{definition.name} Could Not Start',
            message=str(exc),
            detail=(
                'Wait for the active heavy job to reach a terminal state, or cancel it '
                'before starting another heavy execution.'
            ),
            action_url=_jobs_execution_url(
                search=definition.operation,
                queue=definition.queue_name,
            ),
            action_label='Review Active Work',
            action_icon='activity',
            metadata={
                'job_key': job_key,
                'trigger_type': 'manual',
                'reason': 'quota_exceeded',
                'workload_class': definition.workload_class,
            },
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_configuration_job(job_key, operation_feedback=feedback)
        return redirect(url_for('jobs.configuration', job_key=job_key))
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError):
        db.session.rollback()
        logger.exception('Could not dispatch registered job %s.', job_key)
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='job_manual_dispatch',
            status='error',
            title=f'{definition.name} Could Not Start',
            message='KAORI could not dispatch the job to the canonical execution registry.',
            detail='Verify PostgreSQL, Redis, Celery Beat, and the target worker before retrying.',
            action_url=_jobs_execution_url(search=definition.operation, queue=definition.queue_name),
            action_label='Review Job Executions',
            action_icon='list-checks',
            metadata={'job_key': job_key, 'trigger_type': 'manual'},
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_configuration_job(job_key, operation_feedback=feedback)
        return redirect(url_for('jobs.configuration', job_key=job_key))

    if not outcome.accepted:
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='job_manual_dispatch',
            status='warning',
            title=f'{definition.name} Blocked',
            message=outcome.message,
            detail='Resolve the owning domain dependency before retrying this job.',
            action_url=url_for('jobs.configuration', job_key=job_key),
            action_label='Review Job Configuration',
            action_icon='shield-alert',
            metadata={'job_key': job_key, 'trigger_type': 'manual', 'dispatch_status': outcome.status},
            queue_feedback=not is_htmx,
        )
        if is_htmx:
            return _render_configuration_job(job_key, operation_feedback=feedback)
        return redirect(url_for('jobs.configuration', job_key=job_key))

    job = outcome.job
    assert job is not None
    feedback = record_operational_activity(
        user_id=int(current_user.id),
        event_type='job_manual_dispatch',
        status='success' if outcome.created else 'info',
        title=f'{definition.name} Queued' if outcome.created else f'{definition.name} Already Active',
        message=outcome.message,
        detail=definition.safety_summary,
        action_url=_jobs_execution_url(search=definition.operation, queue=definition.queue_name),
        action_label='Open Job Execution',
        action_icon='list-checks',
        metadata={
            'job_key': job_key,
            'job_execution_id': job.id,
            'job_public_id': job.public_id,
            'celery_task_id': job.celery_task_id,
            'trigger_type': 'manual',
            'created': outcome.created,
        },
        queue_feedback=not is_htmx,
    )
    if is_htmx:
        return _render_configuration_job(
            job_key,
            operation_feedback=feedback,
        )
    return redirect(url_for('jobs.configuration', job_key=job_key))


@bp.post('/executions/<string:public_id>/cancel')
@permission_required('jobs.cancel')
def cancel_execution(public_id: str) -> ResponseReturnValue:
    job = JobExecution.query.filter_by(public_id=public_id).first_or_404()
    is_htmx = request.headers.get('HX-Request') == 'true'
    if job.is_active:
        previous_status = job.status
        try:
            cancel_job_execution(job, terminate=False)
        except JobCancellationNotAllowed as exc:
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='job_cancellation_rejected',
                status='warning',
                title='Job Cancellation Unavailable',
                message='KAORI did not interrupt the active provider operation.',
                detail=str(exc),
                action_url=url_for('jobs.executions'),
                action_label='Review Jobs',
                action_icon='list-checks',
                metadata={'job_execution_id': job.id, 'job_public_id': job.public_id},
                queue_feedback=not is_htmx,
            )
        else:
            canceled_before_start = previous_status == 'queued' and job.status == 'canceled'
            if canceled_before_start and job.job_type == 'integration_operation' and job.celery_task_id:
                payload = job.payload_json or {}
                try:
                    release_validation_job = getattr(
                        import_module('app.integrations.validation.state'),
                        'release_validation_job',
                    )
                    release_validation_job(
                        task_id=job.celery_task_id,
                        integration_type=str(job.integration_type or payload.get('integration_type') or ''),
                        operation=job.operation,
                        integration_instance_id=int(
                            job.integration_instance_id or payload.get('integration_instance_id') or 0
                        ),
                        binding_id=payload.get('binding_id'),
                    )
                except Exception:
                    current_app.logger.exception(
                        'Could not release integration lock for canceled job %s.',
                        job.public_id,
                    )
            feedback = record_operational_activity(
                user_id=int(current_user.id),
                event_type='job_canceled' if canceled_before_start else 'job_cancellation_requested',
                status='warning',
                title='Job Canceled' if canceled_before_start else 'Job Cancellation Requested',
                message=(
                    f'KAORI canceled {job_operation_label(job.operation)} before worker execution.'
                    if canceled_before_start
                    else f'KAORI requested cancellation for {job_operation_label(job.operation)}.'
                ),
                detail=(
                    'The queued task was revoked and its active deduplication slot was released.'
                    if canceled_before_start
                    else 'Running jobs stop at their next cooperative cancellation checkpoint.'
                ),
                action_url=url_for('jobs.executions'),
                action_label='Review Jobs',
                action_icon='list-checks',
                metadata={
                    'job_execution_id': job.id,
                    'job_public_id': job.public_id,
                    'previous_status': previous_status,
                    'current_status': job.status,
                },
                queue_feedback=not is_htmx,
            )
    else:
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='job_cancellation_ignored',
            status='info',
            title='Job Already Completed',
            message='KAORI did not request cancellation because the job is already terminal.',
            detail=f'Current status: {job.status.replace("_", " ").title()}.',
            action_url=url_for('jobs.executions'),
            action_label='Review Jobs',
            action_icon='list-checks',
            metadata={'job_execution_id': job.id, 'job_public_id': job.public_id},
            queue_feedback=not is_htmx,
        )

    if is_htmx:
        fragment = request.form.get('fragment', 'workspace').strip()
        context = build_job_execution_context(
            page=request.form.get('page', 1, type=int) or 1,
            per_page=request.form.get('per_page', 5, type=int) or 5,
            status=request.form.get('status', '').strip(),
            workload=request.form.get('workload', '').strip(),
            queue=request.form.get('queue', '').strip(),
            search=request.form.get('search', '').strip(),
            tab=request.form.get('execution_tab', 'active').strip(),
        )
        context['operation_feedback'] = feedback
        context['notification_context'] = get_navigation_notification_context(user_id=int(current_user.id))
        return _render_execution_fragment(context, fragment)
    return redirect(url_for('jobs.executions'))

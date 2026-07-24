from __future__ import annotations

from flask import Blueprint, current_app, render_template, request, send_file, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.extensions.db import db
from app.jobs.dispatcher import enqueue_canonical_job
from app.notifications.service import record_operational_activity
from app.rbac.decorators import permission_required
from app.retention.domains import DOMAIN_FACTORIES, get_archive_domain
from app.retention.policy_service import update_policy
from app.retention.presentation import build_data_lifecycle_context
from app.retention.service import get_archive_download_path, verify_archive_artifact
from app.retention.tasks import run_domain_retention_task

bp = Blueprint('data_lifecycle', __name__)


def _int(name: str, default: int) -> int:
    try:
        return int(request.values.get(name, default))
    except (TypeError, ValueError):
        return default


def _domain() -> str:
    value = str(request.values.get('domain') or 'operational_activity').strip().lower().replace('-', '_')
    return value if value in DOMAIN_FACTORIES else 'operational_activity'


def _context(*, feedback: dict | None = None, preview: bool = False) -> dict:
    return build_data_lifecycle_context(
        selected_domain=_domain(),
        active_tab=str(request.values.get('tab') or 'policies'),
        include_preview=preview or request.values.get('preview') == '1',
        archive_page=_int('archive_page', 1),
        archive_per_page=_int('archive_per_page', 5),
        archive_status=str(request.values.get('archive_status') or 'all'),
        archive_trigger=str(request.values.get('archive_trigger') or 'all'),
        archive_mode=str(request.values.get('archive_mode') or 'all'),
        archive_storage=str(request.values.get('archive_storage') or 'all'),
        archive_search=str(request.values.get('archive_search') or ''),
        archive_domain=str(request.values.get('archive_domain') or 'all'),
        feedback=feedback,
    )


@bp.get('/')
@permission_required('settings.view_data_lifecycle')
def index() -> ResponseReturnValue:
    context = _context()
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'data-lifecycle-history':
            return render_template('settings/data_lifecycle/partials/_history.html', lifecycle=context)
        if target == 'data-lifecycle-domain-workspace':
            return render_template('settings/data_lifecycle/partials/_domain_workspace.html', lifecycle=context)
    return render_template('settings/data_lifecycle/index.html', lifecycle=context)


@bp.get('/preview')
@permission_required('settings.view_data_lifecycle')
def preview() -> ResponseReturnValue:
    return render_template(
        'settings/data_lifecycle/partials/_domain_workspace.html',
        lifecycle=_context(preview=True),
    )


@bp.post('/policy')
@permission_required('settings.manage_data_lifecycle')
def save_policy() -> ResponseReturnValue:
    domain_name = _domain()
    domain = get_archive_domain(domain_name)
    fallback = domain.build_policy()
    try:
        settings = dict(fallback.settings or {})
        if domain_name == 'job_execution':
            settings['workload_retention_days'] = {
                'runtime': max(_int('runtime_retention_days', 30), 1),
                'validation': max(_int('validation_retention_days', 30), 1),
                'analytics': max(_int('analytics_retention_days', 90), 1),
                'forecasting': max(_int('forecasting_retention_days', 180), 1),
                'standard': max(_int('hot_retention_days', 90), 1),
            }
            settings['failed_retention_days'] = max(_int('failed_retention_days', 90), 1)
            settings['preserve_result_references'] = True
        update_policy(
            domain=domain_name,
            fallback=fallback,
            enabled=request.form.get('enabled') == 'on',
            hot_retention_days=_int('hot_retention_days', fallback.retention_days),
            archive_retention_days=_int('archive_retention_days', fallback.archive_retention_days),
            batch_size=_int('batch_size', fallback.batch_size),
            operation_mode=str(request.form.get('operation_mode') or 'archive_and_cleanup'),
            schedule_enabled=request.form.get('schedule_enabled') == 'on',
            schedule_hour=_int('schedule_hour', 2),
            schedule_minute=_int('schedule_minute', 0),
            protect_unreviewed=request.form.get('protect_unreviewed') == 'on',
            protected_max_days=(
                _int('protected_max_days', fallback.protected_max_days or fallback.retention_days)
                if domain_name == 'operational_activity'
                else None
            ),
            settings=settings,
        )
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='data_lifecycle_policy_updated',
            status='success',
            title='Data lifecycle policy updated',
            message=f'{domain_name.replace("_", " ").title()} now uses the updated retention and archive policy.',
            detail='The new boundary is applied by future previews and background lifecycle jobs.',
            action_url=url_for('settings.data_lifecycle.index', domain=domain_name),
            action_label='Open Data Lifecycle',
            action_icon='archive-restore',
            metadata={'domain': domain_name},
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not update data lifecycle policy.')
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='data_lifecycle_policy_update_failed',
            status='error',
            title='Data lifecycle policy update failed',
            message=f'The policy was not changed because of {type(exc).__name__}.',
            detail='Review the submitted retention values and application logs before retrying.',
            action_url=url_for('settings.data_lifecycle.index', domain=domain_name),
            metadata={'domain': domain_name, 'error_type': type(exc).__name__},
        )
    return render_template(
        'settings/data_lifecycle/partials/_domain_workspace.html',
        lifecycle=_context(feedback=feedback),
    )


@bp.post('/run')
@permission_required('settings.manage_data_lifecycle')
def run() -> ResponseReturnValue:
    domain_name = _domain()
    mode = str(request.form.get('mode') or 'archive_only')
    cleanup = mode == 'archive_and_cleanup'
    try:
        domain = get_archive_domain(domain_name)
        policy = domain.build_policy()
        job, created = enqueue_canonical_job(
            task=run_domain_retention_task,
            task_kwargs={
                'domain_name': domain_name,
                'cleanup': cleanup,
                'trigger_type': 'manual',
                'requested_by_user_id': current_user.id,
            },
            job_type='data_lifecycle',
            operation=mode,
            queue_name=str(current_app.config.get('RETENTION_CELERY_QUEUE', 'maintenance')),
            workload_class='maintenance',
            requested_by_user_id=current_user.id,
            resource_group=f'data-lifecycle:{domain_name}',
            scope_type='data_domain',
            scope_key=domain_name,
            parameters={
                'domain': domain_name,
                'mode': mode,
                'retention_days': policy.retention_days,
                'archive_retention_days': policy.archive_retention_days,
            },
            payload={'trigger_type': 'manual'},
            max_attempts=2,
        )
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='data_lifecycle_execution_requested',
            status='info',
            title='Data lifecycle execution queued' if created else 'Data lifecycle execution already active',
            message=(
                f'{domain_name.replace("_", " ").title()} archive processing was queued.'
                if created
                else f'{domain_name.replace("_", " ").title()} already has an active lifecycle job; this request was attached to it.'
            ),
            detail='KAORI will write and verify the archive before cleanup is allowed to begin.',
            action_url=url_for('settings.data_lifecycle.index', tab='history', archive_domain=domain_name),
            action_label='Review Execution History',
            action_icon='history',
            metadata={
                'domain': domain_name,
                'mode': mode,
                'job_execution_id': job.id,
                'celery_task_id': job.celery_task_id,
                'created': created,
            },
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not queue data lifecycle execution.')
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='data_lifecycle_execution_queue_failed',
            status='error',
            title='Data lifecycle execution was not queued',
            message=f'The request failed because of {type(exc).__name__}.',
            detail='No archive was created and no hot record was removed.',
            action_url=url_for('settings.data_lifecycle.index', domain=domain_name),
            metadata={'domain': domain_name, 'error_type': type(exc).__name__},
        )
    return render_template(
        'settings/data_lifecycle/partials/_domain_workspace.html',
        lifecycle=_context(feedback=feedback),
    )


@bp.post('/archives/<archive_id>/verify')
@permission_required('settings.manage_data_lifecycle')
def verify(archive_id: str) -> ResponseReturnValue:
    try:
        result = verify_archive_artifact(archive_id)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='data_lifecycle_archive_verified',
            status='success',
            title='Archive verification completed',
            message='KAORI verified the archive data and manifest checksums.',
            detail='The archive remains available according to its domain archive-retention policy.',
            action_url=url_for('settings.data_lifecycle.index', tab='history'),
            metadata=result,
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Could not verify lifecycle archive.')
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='data_lifecycle_archive_verification_failed',
            status='error',
            title='Archive verification failed',
            message=f'The archive could not be verified because of {type(exc).__name__}.',
            detail='No hot record was modified.',
            action_url=url_for('settings.data_lifecycle.index', tab='history'),
            metadata={'archive_id': archive_id, 'error_type': type(exc).__name__},
        )
    context = _context(feedback=feedback)
    context['active_tab'] = 'history'
    return render_template('settings/data_lifecycle/partials/_history.html', lifecycle=context)


@bp.get('/archives/<archive_id>/download')
@permission_required('settings.export_data_lifecycle')
def download(archive_id: str) -> ResponseReturnValue:
    artifact, path = get_archive_download_path(archive_id, kind=request.args.get('kind', 'data'))
    return send_file(path, as_attachment=True, download_name=path.name)

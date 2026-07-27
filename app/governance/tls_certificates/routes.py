from __future__ import annotations

import json
import logging

from celery.exceptions import CeleryError
from flask import abort, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.cluster.onboarding import has_registered_clusters
from app.extensions.db import db
from app.governance.tls_certificates.service import (
    get_tls_certificate_detail,
    get_tls_certificate_page,
)
from app.governance.tls_certificates.sync_state import build_tls_sync_state
from app.governance.tls_certificates.toast import (
    get_visible_tls_sync_job,
    present_tls_sync_toast,
)
from app.jobs.dispatcher import dispatch_registered_job
from app.jobs.service import JobQuotaExceeded
from app.models.audit import AuditEvent
from app.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)

_SYNC_FILTER_KEYS = ('cluster_id', 'namespace', 'status', 'search', 'page', 'per_page')


def _sync_filter_args(source) -> dict[str, str]:
    return {key: (source.get(key) or '').strip() for key in _SYNC_FILTER_KEYS}


def _record_dispatch_audit(
    *,
    action_status: str,
    summary: str,
    cluster_id: str | None,
    job=None,
    metadata: dict[str, object] | None = None,
) -> None:
    event = AuditEvent()
    event.actor_user_id = int(current_user.id)
    event.target_type = 'job_execution' if job is not None else 'tls_certificate_inventory'
    event.target_id = job.public_id if job is not None else (cluster_id or 'all_clusters')
    event.action = f'governance_tls_secret_sync_dispatch_{action_status}'
    event.summary = summary[:255]
    event.metadata_json = {
        'cluster_id': cluster_id,
        'job_execution_id': job.id if job is not None else None,
        'job_public_id': job.public_id if job is not None else None,
        'dispatch_status': action_status,
        **(metadata or {}),
    }
    try:
        db.session.add(event)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Could not persist TLS sync dispatch audit event.')


def _render_sync_response(
    *,
    filter_args: dict[str, str],
    feedback: dict[str, object] | None = None,
    status_code: int = 202,
):
    payload = get_tls_certificate_page(filter_args)
    rendered_feedback = None
    if feedback is not None:
        rendered_feedback = {
            **feedback,
            'notification_context': get_navigation_notification_context(
                user_id=int(current_user.id),
            ),
        }
    return (
        render_template(
            'governance/tls_certificates/partials/_inventory_scope.html',
            payload=payload,
            sync_feedback=rendered_feedback,
        ),
        status_code,
    )


@permission_required('tls_certificates.view')
def tls_certificates_index():
    payload = get_tls_certificate_page(request.args)
    partial_mode = request.args.get('partial_mode')

    if partial_mode == 'content':
        return render_template(
            'governance/tls_certificates/partials/_page_content.html',
            payload=payload,
        )

    if partial_mode == 'inventory_scope':
        return render_template(
            'governance/tls_certificates/partials/_inventory_scope.html',
            payload=payload,
        )

    if partial_mode == 'table':
        return render_template(
            'governance/tls_certificates/partials/_table.html',
            payload=payload,
        )

    return render_template(
        'governance/tls_certificates/index.html',
        payload=payload,
    )


@permission_required('tls_certificates.sync')
def tls_certificates_active_sync():
    """Backward-compatible endpoint retained after active progress returned to the page panel."""
    return ''


@permission_required('tls_certificates.sync')
def tls_certificates_sync_status(public_id: str):
    job = get_visible_tls_sync_job(public_id=public_id, user_id=int(current_user.id))
    if job is None:
        abort(404)

    filter_args = _sync_filter_args(request.args)
    payload = {
        'filters': filter_args,
        'sync_state': build_tls_sync_state(cluster_id=filter_args['cluster_id'] or None),
    }
    sync = present_tls_sync_toast(job)

    response = make_response(
        render_template(
            'governance/tls_certificates/partials/_sync_panel_response.html',
            payload=payload,
            sync_result=None if sync['is_active'] else sync,
        )
    )
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    if sync['is_active']:
        return response

    response.headers['HX-Trigger-After-Swap'] = json.dumps(
        {
            'tlsInventorySyncFinished': True,
            'kaori:notifications-changed': True,
        }
    )
    return response


@permission_required('tls_certificates.view')
def tls_certificates_detail(certificate_id: int):
    if has_registered_clusters() is False:
        return redirect(url_for('governance.tls_certificates'))

    record = get_tls_certificate_detail(certificate_id)
    if record is None:
        record_operational_activity(
            user_id=current_user.id,
            event_type='governance_tls_certificate_record_missing',
            status='warning',
            title='TLS certificate record was not found',
            message=(
                'The requested TLS certificate record is no longer available. '
                'Refresh the inventory and select a current record.'
            ),
            action_url=url_for('governance.tls_certificates'),
            metadata={'certificate_id': certificate_id},
            queue_feedback=True,
        )
        return redirect(url_for('governance.tls_certificates'))

    return render_template(
        'governance/tls_certificates/detail.html',
        record=record,
    )


@permission_required('tls_certificates.sync')
def tls_certificates_sync():
    filter_args = _sync_filter_args(request.form)
    cluster_id = filter_args['cluster_id'] or None
    is_htmx = request.headers.get('HX-Request') == 'true'

    try:
        outcome = dispatch_registered_job(
            job_key='governance.tls_certificates.sync',
            trigger_type='manual',
            requested_by_user_id=int(current_user.id),
            parameters={'cluster_id': cluster_id} if cluster_id else None,
        )
    except JobQuotaExceeded as exc:
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='governance_tls_secret_sync_dispatch',
            status='warning',
            title='TLS Secret Sync Could Not Start',
            message=str(exc),
            detail='Wait for the active inventory job to finish or review Jobs & Executions.',
            action_url=url_for('jobs.executions', queue='inventory', search='tls_certificate_sync'),
            action_label='Review Active Jobs',
            action_icon='activity',
            metadata={'cluster_id': cluster_id, 'reason': 'quota_exceeded'},
            queue_feedback=not is_htmx,
        )
        _record_dispatch_audit(
            action_status='quota_exceeded',
            summary='TLS Secret synchronization could not start because the active job quota was reached.',
            cluster_id=cluster_id,
            metadata={'reason': str(exc)},
        )
        if is_htmx:
            return _render_sync_response(filter_args=filter_args, feedback=feedback, status_code=409)
        return redirect(url_for('governance.tls_certificates', **filter_args))
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError):
        logger.exception('Could not enqueue TLS certificate synchronization.')
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='governance_tls_secret_sync_dispatch',
            status='error',
            title='TLS Secret Sync Could Not Start',
            message='KAORI could not dispatch TLS certificate synchronization to the inventory worker.',
            detail='Verify PostgreSQL, Redis, Celery Beat, and the inventory worker before retrying.',
            action_url=url_for('jobs.executions', queue='inventory', search='tls_certificate_sync'),
            action_label='Review Job Executions',
            action_icon='list-checks',
            metadata={'cluster_id': cluster_id, 'reason': 'dispatch_failed'},
            queue_feedback=not is_htmx,
        )
        _record_dispatch_audit(
            action_status='failed',
            summary='TLS Secret synchronization could not be dispatched to the inventory worker.',
            cluster_id=cluster_id,
            metadata={'reason': 'worker_dispatch_failed'},
        )
        if is_htmx:
            return _render_sync_response(filter_args=filter_args, feedback=feedback, status_code=503)
        return redirect(url_for('governance.tls_certificates', **filter_args))

    if not outcome.accepted or outcome.job is None:
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='governance_tls_secret_sync_dispatch',
            status='warning',
            title='TLS Secret Sync Blocked',
            message=outcome.message,
            detail='Enable a canonical Kubernetes binding for the selected scope before retrying.',
            action_url=url_for('integrations.kubernetes'),
            action_label='Review Kubernetes Connections',
            action_icon='server-cog',
            metadata={'cluster_id': cluster_id, 'dispatch_status': outcome.status},
            queue_feedback=not is_htmx,
        )
        _record_dispatch_audit(
            action_status='blocked',
            summary='TLS Secret synchronization was blocked by the current integration readiness state.',
            cluster_id=cluster_id,
            metadata={'dispatch_status': outcome.status},
        )
        if is_htmx:
            return _render_sync_response(filter_args=filter_args, feedback=feedback, status_code=409)
        return redirect(url_for('governance.tls_certificates', **filter_args))

    feedback = record_operational_activity(
        user_id=int(current_user.id),
        event_type='governance_tls_secret_sync_dispatch',
        status='success' if outcome.created else 'info',
        title='TLS Secret Sync Queued' if outcome.created else 'TLS Secret Sync Already Active',
        message=outcome.message,
        detail='The inventory worker collects TLS Secrets and Ingress usage outside the web request.',
        action_url=url_for('jobs.executions', queue='inventory', search=outcome.job.public_id),
        action_label='Review Job Progress',
        action_icon='activity',
        metadata={
            'cluster_id': cluster_id,
            'job_execution_id': outcome.job.id,
            'job_public_id': outcome.job.public_id,
            'trigger_type': 'manual',
            'created': outcome.created,
        },
        queue_feedback=not is_htmx,
    )
    _record_dispatch_audit(
        action_status='queued' if outcome.created else 'already_active',
        summary=(
            'TLS Secret synchronization was queued for the inventory worker.'
            if outcome.created
            else 'TLS Secret synchronization was already active when another request was received.'
        ),
        cluster_id=cluster_id,
        job=outcome.job,
        metadata={'created': outcome.created, 'trigger_type': 'manual'},
    )
    if is_htmx:
        return _render_sync_response(
            filter_args=filter_args,
            feedback=feedback,
        )
    return redirect(url_for('governance.tls_certificates', **filter_args))

from __future__ import annotations

import logging

from celery.exceptions import CeleryError
from flask import redirect, render_template, request, url_for
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.cluster.onboarding import has_registered_clusters
from app.governance.tls_certificates.service import (
    get_tls_certificate_detail,
    get_tls_certificate_page,
)
from app.jobs.dispatcher import dispatch_registered_job
from app.jobs.service import JobQuotaExceeded
from app.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)


def _render_sync_response(
    *,
    filter_args: dict[str, str],
    feedback: dict[str, object],
    status_code: int = 202,
):
    payload = get_tls_certificate_page(filter_args)
    return (
        render_template(
            'governance/tls_certificates/partials/_inventory_scope.html',
            payload=payload,
            sync_feedback={
                **feedback,
                'notification_context': get_navigation_notification_context(
                    user_id=int(current_user.id),
                ),
            },
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
            message='The requested TLS certificate record is no longer available. Refresh the inventory and select a current record.',
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
    filter_args = {
        key: (request.form.get(key) or '').strip()
        for key in ('cluster_id', 'namespace', 'status', 'search', 'page', 'per_page')
    }
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
        action_url=url_for('jobs.executions', queue='inventory', search='tls_certificate_sync'),
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
    if is_htmx:
        return _render_sync_response(filter_args=filter_args, feedback=feedback)
    return redirect(url_for('governance.tls_certificates', **filter_args))

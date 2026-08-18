from __future__ import annotations

import json
import logging
from typing import Any

from celery.exceptions import CeleryError
from flask import (
    abort,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError

from app.access.rbac.decorators import permission_required
from app.kubernetes.cluster.onboarding import has_registered_clusters
from app.kubernetes.governance.tls_certificates.audit import record_tls_sync_dispatch_audit
from app.kubernetes.governance.tls_certificates.job_presentation import get_visible_tls_sync_job, present_tls_sync_job
from app.kubernetes.governance.tls_certificates.readiness import check_tls_governance_schema_readiness
from app.kubernetes.governance.tls_certificates.service import get_tls_certificate_detail, get_tls_certificate_page
from app.kubernetes.governance.tls_certificates.sync_state import build_tls_sync_state
from app.platform_operations.jobs.dispatcher import dispatch_registered_job
from app.platform_operations.jobs.service import JobQuotaExceeded
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    queue_transient_feedback,
    record_operational_activity,
)

logger = logging.getLogger(__name__)

_SYNC_FILTER_KEYS = ('cluster_id', 'namespace', 'status', 'search', 'page', 'per_page')


def _clusterless_read_response():
    if has_registered_clusters() is not False:
        return None
    if request.headers.get('HX-Request') == 'true' or request.args.get('partial_mode'):
        return render_template('components/cluster/_onboarding_banner.html')
    return None


def _clusterless_detail_response():
    if has_registered_clusters() is not False:
        return None
    if request.headers.get('HX-Request') == 'true':
        return render_template('components/cluster/_onboarding_banner.html')
    return redirect(url_for('governance.tls_certificates'))


def _clusterless_sync_response():
    if has_registered_clusters() is not False:
        return None
    if request.headers.get('HX-Request') == 'true':
        return render_template('components/cluster/_onboarding_banner.html')

    record_operational_activity(
        user_id=current_user.id,
        event_type='governance_tls_cluster_required',
        status='warning',
        title='Kubernetes Cluster Setup Required',
        message='Add a Kubernetes cluster before using TLS certificate governance actions in KAORI.',
        action_url=url_for('integrations.kubernetes'),
        queue_feedback=True,
    )
    return redirect(url_for('governance.tls_certificates'))


def _sync_filter_args(source) -> dict[str, Any]:
    return {key: (source.get(key) or '').strip() for key in _SYNC_FILTER_KEYS}


def _record_dispatch_audit(
    *,
    action_status: str,
    summary: str,
    cluster_id: str | None,
    job=None,
    metadata: dict[str, object] | None = None,
) -> None:
    record_tls_sync_dispatch_audit(
        actor_user_id=int(current_user.id),
        action_status=action_status,
        summary=summary,
        cluster_id=cluster_id,
        job=job,
        metadata=metadata,
    )


def _render_sync_response(
    *,
    filter_args: dict[str, Any],
    feedback: dict[str, object] | None = None,
    sync_progress: dict[str, object] | None = None,
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
            'kubernetes/governance/tls_certificates/partials/_page_workspace.html',
            payload=payload,
            sync_feedback=rendered_feedback,
            sync_progress=sync_progress,
        ),
        status_code,
    )


@permission_required('tls_certificates.view')
def tls_certificates_index():
    clusterless_response = _clusterless_read_response()
    if clusterless_response is not None:
        return clusterless_response

    payload = get_tls_certificate_page(request.args)
    partial_mode = request.args.get('partial_mode')

    if partial_mode == 'content':
        return render_template(
            'kubernetes/governance/tls_certificates/partials/_page_content.html',
            payload=payload,
        )

    if partial_mode == 'page_workspace':
        return render_template(
            'kubernetes/governance/tls_certificates/partials/_page_workspace.html',
            payload=payload,
        )

    if partial_mode == 'table':
        return render_template(
            'kubernetes/governance/tls_certificates/partials/_table.html',
            payload=payload,
        )

    return render_template(
        'kubernetes/governance/tls_certificates/index.html',
        payload=payload,
    )


@permission_required('tls_certificates.sync')
def tls_certificates_sync_status(public_id: str):
    clusterless_response = _clusterless_read_response()
    if clusterless_response is not None:
        return clusterless_response

    job = get_visible_tls_sync_job(public_id=public_id, user_id=int(current_user.id))
    if job is None:
        abort(404)

    filter_args = _sync_filter_args(request.args)
    schema_readiness = check_tls_governance_schema_readiness()
    if not schema_readiness.ready:
        page_payload = get_tls_certificate_page(filter_args)
        return render_template(
            'kubernetes/governance/tls_certificates/partials/_schema_blocker.html',
            payload=page_payload,
        ), 409

    payload = {
        'filters': filter_args,
        'sync_state': build_tls_sync_state(cluster_id=filter_args['cluster_id'] or None),
    }
    sync = present_tls_sync_job(job, user_id=int(current_user.id))
    if request.args.get('surface') == 'toast':
        if sync['is_active']:
            response = make_response(
                render_template(
                    'kubernetes/governance/tls_certificates/partials/_sync_progress_toast.html',
                    sync=sync,
                    toast_oob=False,
                )
            )
        else:
            response = make_response(
                render_template(
                    'components/operational_toast.html',
                    feedback_id=f'tls-sync-{sync["public_id"]}',
                    status=sync['status'],
                    title=sync['title'],
                    message=sync['message'],
                    detail=sync['detail'],
                    view_url=url_for('governance.tls_certificates'),
                    action_label='View TLS Inventory',
                    action_icon='shield-check',
                    total_count=sync['total_count'],
                    synced_count=sync['synced_count'],
                    failed_count=sync['failed_count'],
                    duration_seconds=sync['duration_seconds'],
                    completed_label=sync['completed_label'],
                    activity_audit_saved=sync['activity_audit_saved'],
                    activity_audit_expected=True,
                    notification_deck_visible=sync['notification_deck_visible'],
                    delivery='toast',
                )
            )
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        return response

    response = make_response(
        render_template(
            'kubernetes/governance/tls_certificates/partials/_sync_panel_response.html',
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
    clusterless_response = _clusterless_detail_response()
    if clusterless_response is not None:
        return clusterless_response

    record = get_tls_certificate_detail(certificate_id)
    if record is None:
        record_operational_activity(
            user_id=current_user.id,
            event_type='governance_tls_certificate_record_missing',
            status='warning',
            title='TLS Certificate Record Was Not Found',
            message=(
                'The requested TLS certificate record is no longer available. '
                'Refresh the inventory and select a current record.'
            ),
            action_url=url_for('governance.tls_certificates'),
            metadata={
                'certificate_id': certificate_id,
                'feedback_delivery': 'toast',
            },
            queue_feedback=True,
            delivery_policy=OperationalDeliveryPolicy.PERSISTENT,
        )
        return redirect(url_for('governance.tls_certificates'))

    if request.headers.get('HX-Request') == 'true':
        return render_template(
            'kubernetes/governance/tls_certificates/partials/_detail_content.html',
            record=record,
        )

    return render_template(
        'kubernetes/governance/tls_certificates/detail.html',
        record=record,
    )


@permission_required('tls_certificates.sync')
def tls_certificates_sync():
    clusterless_response = _clusterless_sync_response()
    if clusterless_response is not None:
        return clusterless_response

    filter_args = _sync_filter_args(request.form)
    cluster_id = filter_args['cluster_id'] or None
    is_htmx = request.headers.get('HX-Request') == 'true'
    schema_readiness = check_tls_governance_schema_readiness()
    if not schema_readiness.ready:
        page_payload = get_tls_certificate_page(filter_args)
        if is_htmx:
            return render_template(
                'kubernetes/governance/tls_certificates/partials/_page_workspace.html',
                payload=page_payload,
            ), 409
        return redirect(url_for('governance.tls_certificates', **filter_args))

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
            metadata={
                'cluster_id': cluster_id,
                'reason': 'quota_exceeded',
                'feedback_delivery': 'toast',
            },
            queue_feedback=not is_htmx,
            delivery_policy=OperationalDeliveryPolicy.PERSISTENT,
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
            metadata={
                'cluster_id': cluster_id,
                'reason': 'dispatch_failed',
                'feedback_delivery': 'toast',
            },
            queue_feedback=not is_htmx,
            delivery_policy=OperationalDeliveryPolicy.PERSISTENT,
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
            metadata={
                'cluster_id': cluster_id,
                'dispatch_status': outcome.status,
                'feedback_delivery': 'toast',
            },
            queue_feedback=not is_htmx,
            delivery_policy=OperationalDeliveryPolicy.PERSISTENT,
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

    sync_progress = present_tls_sync_job(outcome.job, user_id=int(current_user.id))
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
            sync_progress=sync_progress,
        )
    queue_transient_feedback(
        status='success' if outcome.created else 'info',
        title='TLS Secret Sync Queued' if outcome.created else 'TLS Secret Sync Already Active',
        message=(
            'The inventory worker is collecting TLS Secret and Ingress relationship evidence.'
            if outcome.created
            else 'The existing TLS Secret sync job remains active.'
        ),
        action_url=url_for('jobs.executions', queue='inventory', search=outcome.job.public_id),
        action_label='View Job Progress',
        action_icon='activity',
    )
    return redirect(url_for('governance.tls_certificates', **filter_args))

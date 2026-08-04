from __future__ import annotations

import logging
from time import perf_counter

from celery.exceptions import CeleryError
from flask import flash, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.cluster.sync_state import build_cluster_sync_snapshot
from app.jobs.dispatcher import dispatch_registered_job
from app.jobs.service import JobQuotaExceeded
from app.models.cluster import Cluster
from app.notifications.service import get_navigation_notification_context, record_operational_activity

logger = logging.getLogger(__name__)


def _htmx_dispatch_response(*, response_status: int = 204) -> ResponseReturnValue:
    """Return an eventless response for a Quick Action dispatch.

    Quick Actions only enqueue canonical worker jobs. Notification Center state is
    derived from committed ``JobExecution`` and ``Notification`` rows by the normal
    15-second snapshot cycle; the dispatch response must not open the drawer, switch
    tabs, or force an immediate snapshot request.
    """

    response = make_response('', response_status)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


def sync_snapshot_visible_to_user(snapshot: dict, *, user_id: int) -> bool:
    """Return whether a fleet-sync toast belongs to the current user.

    Scheduled inventory synchronization has no requesting user and remains
    observable through Jobs & Executions and Activity Audit only. Manual fleet
    synchronization is restored only for the user who started it.
    """
    requester = snapshot.get('requested_by_user_id')
    try:
        return requester is not None and int(requester) == int(user_id)
    except (TypeError, ValueError):
        return False


def render_sync_snapshot(
    snapshot: dict,
    *,
    response_status: int = 200,
) -> ResponseReturnValue:
    template = 'components/navigation/_quick_sync_status.html'
    context = {'sync': snapshot}
    if not snapshot['is_active']:
        template = 'components/navigation/_quick_sync_result.html'
        context = {
            'task_id': snapshot.get('task_id'),
            'status': snapshot.get('status') or 'info',
            'title': snapshot.get('title') or 'Kubernetes sync finished',
            'message': snapshot.get('message') or 'The background synchronization task has finished.',
            'detail': snapshot.get('detail'),
            'view_url': url_for('integrations.kubernetes'),
            'total_count': snapshot.get('total_count', 0),
            'synced_count': snapshot.get('synced_count', 0),
            'failed_count': snapshot.get('failed_count', 0),
            'duration_seconds': snapshot.get('duration_seconds'),
            'completed_label': 'Completed just now',
            'notification_context': get_navigation_notification_context(user_id=current_user.id),
            'notification_saved': sync_snapshot_visible_to_user(
                snapshot,
                user_id=int(current_user.id),
            ),
        }
    response = make_response(render_template(template, **context), response_status)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


def render_enqueue_error(*, message: str, detail: str, response_status: int) -> ResponseReturnValue:
    return (
        render_template(
            'components/navigation/_quick_sync_result.html',
            status='error',
            title='Kubernetes sync could not start',
            message=message,
            detail=detail,
            view_url=url_for('integrations.kubernetes'),
            total_count=None,
            synced_count=0,
            failed_count=0,
            duration_seconds=None,
            completed_label='Not started',
            notification_saved=False,
        ),
        response_status,
    )


def run_global_inventory_sync() -> ResponseReturnValue:
    started_at = perf_counter()
    is_htmx = request.headers.get('HX-Request') == 'true'
    view_url = url_for('integrations.kubernetes')
    total_count = Cluster.query.count()

    if total_count == 0:
        duration_seconds = round(perf_counter() - started_at, 1)
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_inventory_sync',
            status='warning',
            title='Inventory Sync Skipped',
            message='No Kubernetes clusters are registered yet.',
            detail='Add a Kubernetes cluster before running global inventory sync.',
            action_url=view_url,
            action_label='Add Kubernetes Cluster',
            action_icon='server-cog',
            metadata={
                'feedback_delivery': 'activity_center',
                'total_count': 0,
                'synced_count': 0,
                'failed_count': 0,
                'duration_seconds': duration_seconds,
            },
        )
        if is_htmx:
            return _htmx_dispatch_response(response_status=204)
        flash('No Kubernetes clusters are registered yet.', 'warning')
        return redirect(request.referrer or view_url)

    try:
        outcome = dispatch_registered_job(
            job_key='kubernetes.inventory.sync',
            trigger_type='manual',
            requested_by_user_id=int(current_user.id),
        )
        if not outcome.accepted or outcome.job is None:
            record_operational_activity(
                user_id=int(current_user.id),
                event_type='kubernetes_inventory_sync',
                status='warning',
                title='Inventory Sync Blocked',
                message='No eligible Kubernetes cluster can be synchronized.',
                detail=outcome.message,
                action_url=view_url,
                action_label='Review Kubernetes Integrations',
                action_icon='shield-alert',
                metadata={
                    'feedback_delivery': 'activity_center',
                    'dispatch_status': outcome.status,
                },
            )
            if is_htmx:
                return _htmx_dispatch_response(response_status=204)
            flash(outcome.message, 'warning')
            return redirect(request.referrer or view_url)

        if is_htmx:
            return _htmx_dispatch_response(response_status=202)
        flash(
            'Kubernetes inventory synchronization started in the inventory worker.'
            if outcome.created
            else 'The existing Kubernetes inventory synchronization is already serving this request.',
            'success' if outcome.created else 'info',
        )
        return redirect(request.referrer or view_url)
    except (
        CeleryError,
        JobQuotaExceeded,
        KombuOperationalError,
        OSError,
        RuntimeError,
        SQLAlchemyError,
    ) as exc:
        logger.exception('KAORI could not enqueue the canonical Kubernetes inventory job.')
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_inventory_sync',
            status='error',
            title='Inventory Sync Could Not Start',
            message='The inventory job could not be added to the canonical job registry.',
            detail='Verify PostgreSQL, Redis, and the Celery inventory worker before retrying.',
            action_url=view_url,
            action_label='Review Kubernetes Integrations',
            action_icon='triangle-alert',
            metadata={
                'feedback_delivery': 'activity_center',
                'error_type': type(exc).__name__,
            },
        )
        if is_htmx:
            return _htmx_dispatch_response(response_status=204)
        flash('KAORI could not start the Kubernetes inventory job.', 'danger')
        return redirect(request.referrer or view_url)

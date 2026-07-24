from __future__ import annotations

import logging
from time import perf_counter

from celery.exceptions import CeleryError
from flask import flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.cluster.sync_state import build_cluster_sync_snapshot
from app.jobs.dispatcher import dispatch_registered_job
from app.jobs.service import JobQuotaExceeded
from app.models.cluster import Cluster
from app.notifications.service import create_notification, get_navigation_notification_context

logger = logging.getLogger(__name__)


def render_sync_snapshot(snapshot: dict, *, response_status: int = 200) -> ResponseReturnValue:
    if snapshot['is_active']:
        return (
            render_template('components/navigation/_quick_sync_status.html', sync=snapshot),
            response_status,
        )

    return (
        render_template(
            'components/navigation/_quick_sync_result.html',
            task_id=snapshot.get('task_id'),
            status=snapshot.get('status') or 'info',
            title=snapshot.get('title') or 'Kubernetes sync finished',
            message=snapshot.get('message') or 'The background synchronization task has finished.',
            detail=snapshot.get('detail'),
            view_url=url_for('integrations.kubernetes'),
            total_count=snapshot.get('total_count', 0),
            synced_count=snapshot.get('synced_count', 0),
            failed_count=snapshot.get('failed_count', 0),
            duration_seconds=snapshot.get('duration_seconds'),
            completed_label='Completed just now',
            notification_context=get_navigation_notification_context(user_id=current_user.id),
            notification_saved=(snapshot.get('requested_by_user_id') == current_user.id),
        ),
        response_status,
    )


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
        create_notification(
            user_id=current_user.id,
            event_type='kubernetes_inventory_sync',
            status='warning',
            title='Sync Skipped',
            message='No Kubernetes clusters are registered yet.',
            detail='Add a Kubernetes cluster before running global inventory sync.',
            action_url=view_url,
            metadata={
                'total_count': 0,
                'synced_count': 0,
                'failed_count': 0,
                'duration_seconds': duration_seconds,
            },
        )
        if is_htmx:
            return render_template(
                'components/navigation/_quick_sync_result.html',
                status='warning',
                title='Sync Skipped',
                message='No Kubernetes clusters are registered yet.',
                detail='Add a Kubernetes cluster before running global inventory sync.',
                view_url=view_url,
                total_count=0,
                synced_count=0,
                failed_count=0,
                duration_seconds=duration_seconds,
                completed_label='Completed just now',
                notification_context=get_navigation_notification_context(user_id=current_user.id),
                notification_saved=True,
            )
        flash('No Kubernetes clusters are registered yet.', 'warning')
        return redirect(request.referrer or view_url)

    try:
        outcome = dispatch_registered_job(
            job_key='kubernetes.inventory.sync',
            trigger_type='manual',
            requested_by_user_id=int(current_user.id),
        )
        if not outcome.accepted or outcome.job is None:
            if is_htmx:
                return render_enqueue_error(
                    message='No eligible Kubernetes cluster can be synchronized.',
                    detail=outcome.message,
                    response_status=409,
                )
            flash(outcome.message, 'warning')
            return redirect(request.referrer or view_url)

        snapshot = build_cluster_sync_snapshot(str(outcome.job.celery_task_id))
        if is_htmx:
            return render_sync_snapshot(snapshot, response_status=202)
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
    ):
        logger.exception('KAORI could not enqueue the canonical Kubernetes inventory job.')
        if is_htmx:
            return render_enqueue_error(
                message='The inventory job could not be added to the canonical job registry.',
                detail='Verify PostgreSQL, Redis, and the Celery inventory worker before retrying.',
                response_status=503,
            )
        flash('KAORI could not start the Kubernetes inventory job.', 'danger')
        return redirect(request.referrer or view_url)

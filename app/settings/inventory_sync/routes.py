from __future__ import annotations

import logging

from celery.exceptions import CeleryError
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.cluster.sync_jobs import NoEligibleInventoryTargets, enqueue_all_cluster_inventory_sync
from app.extensions.db import db
from app.inventory.schedule import get_inventory_sync_policy, update_inventory_sync_policy
from app.jobs.service import JobQuotaExceeded
from app.notifications.service import record_operational_activity
from app.rbac.decorators import permission_required
from app.settings.inventory_sync.forms import InventorySyncPolicyForm, ManualInventorySyncForm
from app.settings.inventory_sync.presentation import build_inventory_sync_page_context

bp = Blueprint('inventory_sync', __name__)
logger = logging.getLogger(__name__)


def _jobs_url() -> str:
    return url_for(
        'integrations.jobs',
        tab='registry',
        queue='inventory',
        search='inventory_sync_all',
    )


@bp.route('/', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def index():
    policy = get_inventory_sync_policy()
    form = InventorySyncPolicyForm()
    manual_form = ManualInventorySyncForm()
    if form.validate_on_submit():
        policy = update_inventory_sync_policy(
            enabled=bool(form.enabled.data),
            interval_minutes=int(form.interval_minutes.data or 60),
            user_id=int(current_user.id),
        )
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='inventory_sync_policy_updated',
            status='success',
            title='Inventory Sync Configuration Updated',
            message=(
                f'Automatic inventory sync runs every {policy.interval_minutes} minutes.'
                if policy.enabled
                else 'Automatic inventory sync is disabled. Manual synchronization remains available.'
            ),
            detail='Celery Beat reads this database-backed policy without requiring a scheduler restart.',
            action_url=url_for('settings.inventory_sync.index'),
            action_label='Review Inventory Sync',
            action_icon='refresh-cw',
            metadata={'enabled': policy.enabled, 'interval_minutes': policy.interval_minutes},
            queue_feedback=True,
        )
        return redirect(url_for('settings.inventory_sync.index'))
    if not form.is_submitted():
        form.enabled.data = policy.enabled
        form.interval_minutes.data = policy.interval_minutes

    context = build_inventory_sync_page_context(policy)
    return render_template(
        'settings/inventory_sync/index.html',
        form=form,
        manual_form=manual_form,
        policy=policy,
        jobs_url=_jobs_url(),
        **context,
    )


@bp.post('/run')
@permission_required('clusters.sync')
def run_now():
    form = ManualInventorySyncForm()
    if not form.validate_on_submit():
        return redirect(url_for('settings.inventory_sync.index'))

    try:
        job, created = enqueue_all_cluster_inventory_sync(
            requested_by_user_id=int(current_user.id),
            trigger_type='manual',
        )
    except NoEligibleInventoryTargets:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_inventory_sync',
            status='warning',
            title='Inventory Sync Blocked',
            message='No eligible Kubernetes cluster is available for fleet inventory synchronization.',
            detail='Enable a canonical Kubernetes integration instance and cluster binding before retrying.',
            action_url=url_for('integrations.kubernetes'),
            action_label='Review Kubernetes Integrations',
            action_icon='server-cog',
            metadata={'trigger_type': 'manual', 'eligible_cluster_count': 0},
            queue_feedback=True,
        )
        return redirect(url_for('settings.inventory_sync.index'))
    except (CeleryError, JobQuotaExceeded, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError):
        db.session.rollback()
        logger.exception('Could not enqueue manual fleet inventory synchronization.')
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_inventory_sync',
            status='error',
            title='Inventory Sync Could Not Start',
            message='KAORI could not dispatch the inventory job to the canonical execution registry.',
            detail='Verify PostgreSQL, Redis, Celery Beat, and the inventory worker before retrying.',
            action_url=_jobs_url(),
            action_label='Review Job Executions',
            action_icon='list-checks',
            metadata={'trigger_type': 'manual'},
            queue_feedback=True,
        )
        return redirect(url_for('settings.inventory_sync.index'))

    record_operational_activity(
        user_id=int(current_user.id),
        event_type='kubernetes_inventory_sync',
        status='success' if created else 'info',
        title='Inventory Sync Queued' if created else 'Inventory Sync Already Active',
        message=(
            'A fleet inventory synchronization was added to Job Executions.'
            if created
            else 'Your request was attached to the existing fleet inventory execution.'
        ),
        detail='The canonical inventory worker processes one atomic committed generation per eligible cluster.',
        action_url=_jobs_url(),
        action_label='Open Job Execution',
        action_icon='list-checks',
        metadata={
            'job_execution_id': job.id,
            'job_public_id': job.public_id,
            'celery_task_id': job.celery_task_id,
            'trigger_type': 'manual',
            'created': created,
        },
        queue_feedback=True,
    )
    return redirect(url_for('settings.inventory_sync.index'))

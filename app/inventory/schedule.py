from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.cluster.sync_jobs import NoEligibleInventoryTargets, enqueue_all_cluster_inventory_sync
from app.extensions.db import db
from app.models.inventory_sync import InventorySyncPolicy

DEFAULT_INTERVAL_MINUTES = 60
MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 1440
POLICY_ID = 1


def _utcnow() -> datetime:
    return datetime.now(UTC)


def get_inventory_sync_policy() -> InventorySyncPolicy:
    policy = db.session.get(InventorySyncPolicy, POLICY_ID)
    if policy is None:
        now = _utcnow()
        policy = InventorySyncPolicy(
            id=POLICY_ID,
            enabled=True,
            interval_minutes=DEFAULT_INTERVAL_MINUTES,
            next_run_at=now + timedelta(minutes=DEFAULT_INTERVAL_MINUTES),
        )
        db.session.add(policy)
        db.session.commit()
    return policy


def update_inventory_sync_policy(*, enabled: bool, interval_minutes: int, user_id: int) -> InventorySyncPolicy:
    if not MIN_INTERVAL_MINUTES <= interval_minutes <= MAX_INTERVAL_MINUTES:
        raise ValueError('Inventory sync interval must be between 5 and 1,440 minutes.')
    policy = get_inventory_sync_policy()
    policy.enabled = enabled
    policy.interval_minutes = interval_minutes
    policy.updated_by_user_id = user_id
    policy.next_run_at = _utcnow() + timedelta(minutes=interval_minutes) if enabled else None
    db.session.commit()
    return policy


def dispatch_due_inventory_sync() -> dict[str, object]:
    """Atomically claim one due schedule tick and enqueue a fleet inventory job."""
    now = _utcnow()
    policy = db.session.execute(
        select(InventorySyncPolicy).where(InventorySyncPolicy.id == POLICY_ID).with_for_update()
    ).scalar_one_or_none()
    if policy is None:
        policy = InventorySyncPolicy(
            id=POLICY_ID,
            enabled=True,
            interval_minutes=DEFAULT_INTERVAL_MINUTES,
            next_run_at=now + timedelta(minutes=DEFAULT_INTERVAL_MINUTES),
        )
        db.session.add(policy)
        db.session.commit()
        return {'dispatched': False, 'reason': 'schedule_initialized'}
    if not policy.enabled:
        db.session.rollback()
        return {'dispatched': False, 'reason': 'disabled'}
    if policy.next_run_at is not None and policy.next_run_at > now:
        db.session.rollback()
        return {'dispatched': False, 'reason': 'not_due'}

    policy.next_run_at = now + timedelta(minutes=policy.interval_minutes)
    db.session.commit()

    try:
        job, created = enqueue_all_cluster_inventory_sync(requested_by_user_id=None, trigger_type='scheduled')
    except NoEligibleInventoryTargets:
        return {'dispatched': False, 'reason': 'no_eligible_clusters'}

    policy = db.session.get(InventorySyncPolicy, POLICY_ID)
    if policy is not None:
        policy.last_dispatched_at = now
        db.session.commit()
    return {
        'dispatched': created,
        'reason': 'queued' if created else 'active_job_reused',
        'job_execution_id': job.id,
    }

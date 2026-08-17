from __future__ import annotations

import logging
from datetime import datetime, timedelta

from celery.exceptions import CeleryError
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.models.job import JobPolicy
from app.platform_operations.jobs.audit import record_automatic_job_event
from app.platform_operations.jobs.dispatcher import dispatch_registered_job
from app.platform_operations.jobs.policies.service import ensure_registered_job_policies, utcnow

logger = logging.getLogger(__name__)


def _advance_due_policy(policy: JobPolicy, now: datetime) -> None:
    interval_minutes = int(policy.interval_minutes or 0)
    if interval_minutes < 1:
        raise ValueError(f'Job policy {policy.job_key} has no valid interval.')
    policy.next_run_at = now + timedelta(minutes=interval_minutes)
    policy.last_dispatch_status = 'dispatching'
    policy.last_dispatch_message = 'The due schedule was claimed by the job dispatcher.'


def dispatch_due_job_policies(*, limit: int = 25) -> dict[str, object]:
    """Claim due policies and dispatch registered jobs through the canonical registry."""
    ensure_registered_job_policies()
    now = utcnow()
    due_ids = [
        row[0]
        for row in db.session.execute(
            select(JobPolicy.id)
            .where(
                JobPolicy.enabled.is_(True),
                JobPolicy.next_run_at.isnot(None),
                JobPolicy.next_run_at <= now,
            )
            .order_by(JobPolicy.next_run_at.asc(), JobPolicy.id.asc())
            .limit(limit)
        )
    ]
    results: list[dict[str, object]] = []

    for policy_id in due_ids:
        policy = db.session.execute(
            select(JobPolicy).where(JobPolicy.id == policy_id).with_for_update(skip_locked=True)
        ).scalar_one_or_none()
        if policy is None or not policy.enabled or policy.next_run_at is None or policy.next_run_at > now:
            db.session.rollback()
            continue

        job_key = policy.job_key
        try:
            _advance_due_policy(policy, now)
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            logger.error('Invalid scheduled job policy %s: %s', job_key, exc)
            current = db.session.get(JobPolicy, policy_id)
            if current is not None:
                current.enabled = False
                current.next_run_at = None
                current.last_dispatch_status = 'failed'
                current.last_dispatch_message = str(exc)[:255]
                db.session.commit()
            results.append({'job_key': job_key, 'status': 'failed'})
            continue

        try:
            outcome = dispatch_registered_job(
                job_key=job_key,
                trigger_type='scheduled',
                requested_by_user_id=None,
            )
        except (
            CeleryError,
            KombuOperationalError,
            LookupError,
            OSError,
            RuntimeError,
            SQLAlchemyError,
            ValueError,
        ) as exc:
            db.session.rollback()
            logger.exception('Scheduled job dispatch failed for %s.', job_key)
            current = db.session.get(JobPolicy, policy_id)
            if current is not None:
                current.last_dispatch_status = 'failed'
                current.last_dispatch_message = str(exc)[:255]
                db.session.commit()
            results.append({'job_key': job_key, 'status': 'failed'})
            continue

        if outcome.job is not None and outcome.created:
            record_automatic_job_event(
                outcome.job,
                action='automatic_job_queued',
                summary=f'Automatic {job_key} execution was queued.',
                metadata={'job_key': job_key, 'dispatch_status': outcome.status},
            )
        current = db.session.get(JobPolicy, policy_id)
        if current is not None:
            current.last_dispatch_status = outcome.status
            current.last_dispatch_message = outcome.message[:255]
            if outcome.job is not None:
                current.last_dispatched_at = now
                current.last_job_execution_id = outcome.job.id
            db.session.commit()
        results.append(
            {
                'job_key': job_key,
                'status': outcome.status,
                'job_execution_id': outcome.job.id if outcome.job is not None else None,
            }
        )

    return {
        'checked_at': now.isoformat(),
        'due_count': len(due_ids),
        'processed_count': len(results),
        'results': results,
    }

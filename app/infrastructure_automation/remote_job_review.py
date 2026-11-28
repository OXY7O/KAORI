"""Canonical remote preflight REVIEW job boundary (#5186).

This operation is deliberately different from remote execution and from the
full Kubespray preflight result. No provider material, SSH or Run permission.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.extensions.db import db
from app.infrastructure_automation.remote_preflight_source import REMOTE_CANDIDATE_SHA, review_remote_source_candidate
from app.infrastructure_automation.remote_preflight_target import RemoteTargetReview, review_remote_preflight_target
from app.infrastructure_automation.remote_worker_review import resolve_remote_worker_review
from app.infrastructure_automation.security_review import local_security_review_enabled
from app.models.job import JobExecution
from app.platform_operations.jobs.fingerprint import payload_fingerprint
from app.platform_operations.jobs.service import mark_job_failed, mark_job_running, mark_job_succeeded
from app.platform_operations.notifications.service import stage_operational_activity

REVIEW_OPERATION = 'automation_remote_preflight_review'
REVIEW_RESULT_TYPE = 'automation_remote_preflight_review_v1'
_QUEUE = 'automation'
_FRESHNESS = timedelta(minutes=15)
_HEX = re.compile(r'[a-f0-9]{64}')


class RemoteReviewDenied(ValueError):
    """Sanitized rejection of missing or stale canonical review evidence."""


def _deny() -> RemoteReviewDenied:
    return RemoteReviewDenied('Remote preflight review is unavailable or unqualified.')


def review_enabled() -> bool:
    # Independent local review opt-in, never an execution flag.
    return local_security_review_enabled() and os.getenv('KAORI_LOCAL_REMOTE_PREFLIGHT_REVIEW') == '1'


def review_parameters(target: RemoteTargetReview) -> dict[str, Any]:
    return {
        'schema_version': 1,
        'actor_id': target.actor_id,
        'connection_id': target.connection_id,
        'profile_sha': target.source_sha,
        'remote_candidate_sha': REMOTE_CANDIDATE_SHA,
        'ee_digest': target.ee_digest,
        'inventory_fingerprint': target.inventory_fingerprint,
        'host_registry_fingerprint': target.host_registry_fingerprint,
        'target_review_fingerprint': target.access_fingerprint,
        'execution_authorized': False,
    }


def _job(job_id: int) -> JobExecution | None:
    return db.session.execute(
        select(JobExecution)
        .where(JobExecution.id == job_id)
        .with_for_update(of=JobExecution)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def matches_review_job(
    job: JobExecution | None, *, task_id: str, connection_id: int, now: datetime, running: bool
) -> bool:
    if job is None or not isinstance(now, datetime) or now.utcoffset() is None:
        return False
    return (
        type(connection_id) is int
        and connection_id > 0
        and isinstance(task_id, str)
        and bool(task_id)
        and job.celery_task_id == task_id
        and job.integration_instance_id == connection_id
        and job.integration_type == 'configuration_automation'
        and job.job_type == 'infrastructure_automation'
        and job.operation == REVIEW_OPERATION
        and job.queue_name == _QUEUE
        and job.workload_class == 'validation'
        and job.scope_type == 'ansible_source_connection'
        and job.scope_key == str(connection_id)
        and job.resource_group == f'kubespray:remote-preflight-review:{connection_id}'
        and type(job.requested_by_user_id) is int
        and job.requested_by_user_id > 0
        and job.max_attempts == 1
        and job.status == ('running' if running else 'queued')
        and job.attempt_count == (1 if running else 0)
        and job.cancel_requested_at is None
        and job.completed_at is None
        and job.queued_at.utcoffset() is not None
        and job.queued_at <= now < job.queued_at + _FRESHNESS
        and (job.expires_at is None or (job.expires_at.utcoffset() is not None and now < job.expires_at))
    )


def _target_for_job(job: JobExecution, *, now: datetime) -> RemoteTargetReview:
    actor, connection_id = job.requested_by_user_id, job.integration_instance_id
    if actor is None or connection_id is None:
        raise _deny()
    target = review_remote_preflight_target(actor_id=actor, connection_id=connection_id, now=now)
    if target is None or target.execution_authorized is not False or target.expires_at <= now:
        raise _deny()
    expected = review_parameters(target)
    payload = job.payload_json
    if not isinstance(payload, dict):
        raise _deny()
    actual = {key: value for key, value in payload.items() if key != '_progress'}
    fingerprint = payload_fingerprint(expected)
    if payload_fingerprint(actual) != fingerprint or job.parameter_fingerprint != fingerprint:
        raise _deny()
    if any(
        _HEX.fullmatch(value) is None
        for value in (target.inventory_fingerprint, target.host_registry_fingerprint, target.access_fingerprint)
    ):
        raise _deny()
    return target


def run_remote_preflight_review(*, job_id: int, task_id: str, connection_id: int, worker_identity: str) -> dict[str, str]:
    """Claim one queued review attempt, recheck and commit an audited redacted receipt.

    A Celery hostname is only correlation with an independently configured
    expected worker name. This does not attest the runtime container/image.
    """
    claimed = False
    try:
        if type(job_id) is not int or job_id <= 0 or not review_enabled():
            return {'status': 'blocked'}
        expected_worker = os.getenv('KAORI_LOCAL_REMOTE_REVIEW_WORKER', '')
        source_path = os.getenv('KAORI_LOCAL_REMOTE_REVIEW_SOURCE', '')
        if not expected_worker or worker_identity != expected_worker or not source_path.startswith('/'):
            return {'status': 'blocked'}
        now = datetime.now(UTC)
        job = _job(job_id)
        if job is None or not matches_review_job(job, task_id=task_id, connection_id=connection_id, now=now, running=False):
            return {'status': 'blocked'}
        # The row is already locked; the canonical service commits the claim.
        # Redelivery sees running/attempt 1 and cannot claim it again.
        started = mark_job_running(task_id, message='Checking remote preflight review evidence', stage='review')
        if started is None or started.status != 'running' or started.attempt_count != 1:
            return {'status': 'blocked'}
        claimed = True
        source = review_remote_source_candidate(source_path)
        now = datetime.now(UTC)
        job = _job(job_id)
        if job is None or not matches_review_job(job, task_id=task_id, connection_id=connection_id, now=now, running=True):
            raise _deny()
        target = _target_for_job(job, now=now)
        evidence = resolve_remote_worker_review(source, target, worker_identity=worker_identity, now=now)
        if evidence is None or evidence.execution_authorized is not False:
            raise _deny()
        # Re-read the exact candidate and independent signed artifact before
        # committing. No raw source path, worker token, addresses or keys.
        final_now = datetime.now(UTC)
        final_target = _target_for_job(job, now=final_now)
        final_source = review_remote_source_candidate(source_path)
        final_evidence = resolve_remote_worker_review(
            final_source, final_target, worker_identity=worker_identity, now=final_now
        )
        if (
            review_parameters(final_target) != review_parameters(target)
            or final_source != source
            or final_evidence != evidence
            or not matches_review_job(job, task_id=task_id, connection_id=connection_id, now=final_now, running=True)
        ):
            raise _deny()
        summary = {
            **review_parameters(final_target),
            'source_review_fingerprint': source.fingerprint,
            'worker_review_fingerprint': evidence.fingerprint,
            'expires_at': min(evidence.expires_at, final_target.expires_at).isoformat(),
            'status': 'review_evidence_recorded',
            'runtime_attestation_verified': False,
            'full_preflight_verified': False,
            'credential_material_accessed': False,
            'ssh_executed': False,
            'mutation_authorized': False,
        }
        stage_operational_activity(
            user_id=job.requested_by_user_id,
            event_type='automation_remote_preflight_review_observed',
            status='success',
            title='Remote preflight review evidence recorded',
            message='Review evidence recorded; remote execution remains blocked.',
            metadata={
                'actor_user_id': job.requested_by_user_id,
                'integration_instance_id': connection_id,
                'job_execution_id': job.id,
                'target_review_fingerprint': final_target.access_fingerprint,
                'execution_authorized': False,
            },
            delivery_policy='audit_only',
        )
        finished = mark_job_succeeded(task_id, result_type=REVIEW_RESULT_TYPE, result_summary=summary)
        return {'status': 'succeeded' if finished is not None and finished.status == 'succeeded' else 'blocked'}
    except Exception:
        db.session.rollback()
        if claimed:
            mark_job_failed(task_id, error='Remote preflight review blocked.', error_code='remote_review_unqualified')
        return {'status': 'blocked'}
    finally:
        db.session.rollback()

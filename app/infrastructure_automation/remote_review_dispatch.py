"""Internal canonical dispatch for remote preflight REVIEW, never remote execution."""

from __future__ import annotations

from datetime import UTC, datetime

from app.extensions.db import db
from app.infrastructure_automation.remote_job_review import REVIEW_OPERATION, RemoteReviewDenied, review_enabled, review_parameters
from app.infrastructure_automation.remote_preflight_target import review_remote_preflight_target
from app.infrastructure_automation.tasks import AUTOMATION_QUEUE, materialize_remote_preflight_review
from app.models.job import JobExecution
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job


def dispatch_remote_preflight_review(*, actor_id: int, connection_id: int) -> tuple[JobExecution, bool]:
    """Enqueue only the redacted evidence review under the initiating human.

    No browser route is enabled. Never accepts source paths, worker names,
    inventory, credentials or commands; the worker requalifies canonical
    evidence immediately before committing the review.
    """
    try:
        if not review_enabled() or type(actor_id) is not int or actor_id <= 0 or type(connection_id) is not int or connection_id <= 0:
            raise RemoteReviewDenied('Remote preflight review is unavailable or unqualified.')
        target = review_remote_preflight_target(actor_id=actor_id, connection_id=connection_id, now=datetime.now(UTC))
        if target is None or target.execution_authorized is not False:
            raise RemoteReviewDenied('Remote preflight review is unavailable or unqualified.')
        parameters = review_parameters(target)
        # Never retain domain locks across broker transport/worker inspection.
        # The worker must rederive and compare the full canonical fingerprint.
        db.session.rollback()
        return enqueue_canonical_job(
            task=materialize_remote_preflight_review,
            task_kwargs={'connection_id': connection_id},
            job_type='infrastructure_automation',
            operation=REVIEW_OPERATION,
            queue_name=AUTOMATION_QUEUE,
            workload_class='validation',
            requested_by_user_id=actor_id,
            resource_group=f'kubespray:remote-preflight-review:{connection_id}',
            scope_type='ansible_source_connection',
            scope_key=str(connection_id),
            integration_type='configuration_automation',
            integration_instance_id=connection_id,
            parameters=parameters,
            max_attempts=1,
            dispatch_options=JobDispatchOptions(
                require_registered_worker=True, soft_time_limit_seconds=60, hard_time_limit_seconds=90
            ),
        )
    except Exception:
        db.session.rollback()
        raise

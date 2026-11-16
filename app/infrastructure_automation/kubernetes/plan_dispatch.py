"""Canonical review-only Kubespray Plan dispatch, no remote execution (#4800)."""

from __future__ import annotations

from app.infrastructure_automation.kubernetes.plan_review import (
    PLAN_OPERATION,
    build_kubespray_plan_review,
)
from app.infrastructure_automation.tasks import AUTOMATION_QUEUE, materialize_kubespray_plan_review
from app.integrations.orchestration.configuration_automation.providers.ansible.preflight import (
    committed_kubespray_preflight,
)
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.jobs.dispatcher import (
    JobDispatchOptions,
    enqueue_canonical_job,
)


class KubesprayPlanNotQualified(ValueError):
    """No usable current source, target, worker evidence, or review plan exists."""


def dispatch_kubespray_plan_review(
    connection: IntegrationInstance,
    *,
    user_id: int,
) -> tuple[JobExecution, bool]:
    """Enqueue a pure DB-only materialization; the worker rechecks all sources.

    This endpoint never accepts host addresses, inventory files, extra-vars,
    credentials or arbitrary playbook names from an operator.
    """
    if (
        type(user_id) is not int
        or connection.integration_type != 'configuration_automation'
        or connection.provider_key != 'ansible'
        or not connection.enabled
        or connection.lifecycle_status != 'active'
    ):
        raise KubesprayPlanNotQualified('A qualified active Ansible connection is required.')

    preflight = committed_kubespray_preflight(connection)
    if preflight.state != 'ready_for_review' or not preflight.facts_job_public_id:
        raise KubesprayPlanNotQualified('Current source and remote-host preflight evidence is required.')
    job = JobExecution.query.filter_by(public_id=preflight.facts_job_public_id).first()
    if job is None or job.integration_instance_id != connection.id:
        raise KubesprayPlanNotQualified('Exact canonical preflight record is missing.')
    plan = build_kubespray_plan_review(connection, job)
    if plan.status != 'requires_independent_approval' or not plan.plan_fingerprint:
        raise KubesprayPlanNotQualified('Static target or source evidence is not qualified.')

    return enqueue_canonical_job(
        task=materialize_kubespray_plan_review,
        task_kwargs={'connection_id': connection.id, 'host_preflight_job_id': job.id},
        job_type='infrastructure_automation',
        operation=PLAN_OPERATION,
        queue_name=AUTOMATION_QUEUE,
        workload_class='validation',
        requested_by_user_id=user_id,
        resource_group=f'kubespray:plan-review:{connection.id}',
        scope_type='ansible_source_connection',
        scope_key=str(connection.id),
        integration_type='configuration_automation',
        integration_instance_id=connection.id,
        parameters={
            'plan_fingerprint': plan.plan_fingerprint,
            'host_preflight_job_public_id': job.public_id,
            'source_sha': plan.source_sha,
        },
        max_attempts=1,
        dispatch_options=JobDispatchOptions(
            require_registered_worker=True,
            soft_time_limit_seconds=60,
            hard_time_limit_seconds=90,
        ),
    )

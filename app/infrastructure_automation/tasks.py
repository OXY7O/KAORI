"""Dedicated automation-queue localhost facts task; no remote or mutation path."""

from __future__ import annotations

from importlib import import_module
from tempfile import TemporaryDirectory
from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.infrastructure_automation.kubernetes.plan_review import (
    PLAN_RESULT_TYPE,
    build_kubespray_plan_review,
)
from app.infrastructure_automation.source import (
    INVENTORY,
    OPERATION_ID,
    SOURCE_REPOSITORY,
    AutomationPilotDenied,
    normalize_facts,
    verify_localhost_source,
    verify_read_only_runner_stats,
)
from app.integrations.orchestration.configuration_automation.providers.ansible.preflight import (
    committed_kubespray_preflight,
)
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.jobs.execution import (
    JobCancellationRequested,
    JobExecutionContext,
    JobExecutionUnavailable,
)

AUTOMATION_QUEUE = 'automation'


@shared_task(
    name='app.infrastructure_automation.tasks.collect_localhost_facts',
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def collect_localhost_facts(self: Any, *, source_path: str, source_sha: str, job_execution_id: int) -> dict[str, str]:
    context = JobExecutionContext(task_id=str(self.request.id), job_execution_id=job_execution_id)
    try:
        root = verify_localhost_source(source_path, source_sha)
        context.start(message='Collecting read-only Linux facts from local automation worker', stage='preflight')
        context.checkpoint(message='Approved exact source and local-only inventory verified', stage='execution')
        try:
            ansible_runner = import_module('ansible_runner')
        except ImportError as exc:
            raise AutomationPilotDenied('Pinned Ansible Runner dependency is unavailable') from exc
        # Runner event artifacts are transient, not committed KAORI evidence.
        with TemporaryDirectory(prefix='kaori-automation-localhost-') as private_data_dir:
            runner = ansible_runner.run(
                private_data_dir=private_data_dir,
                project_dir=str(root / 'ansible/playbooks'),
                playbook='linux_host_facts.yml',
                inventory=str(root / INVENTORY),
                limit='localhost',
                quiet=True,
                timeout=120,
                suppress_env_files=True,
                envvars={
                    'ANSIBLE_CONFIG': str(root / 'ansible/ansible.cfg'),
                    'ANSIBLE_HOST_KEY_CHECKING': 'True',
                },
            )
            if runner.status != 'successful' or runner.rc != 0:
                raise AutomationPilotDenied('Runner did not complete the read-only operation')
            verify_read_only_runner_stats(runner.stats)
            facts = normalize_facts(list(runner.events))
        context.succeed(
            result_type='automation_read_only_host_facts',
            result_summary={
                'repository': SOURCE_REPOSITORY,
                'source_sha': source_sha,
                'operation_id': OPERATION_ID,
                'target': 'automation-worker:localhost',
                'environment_attestation': 'NOT VERIFIED',
                'changed': False,
                'readback': 'ansible-setup-facts',
                'facts': facts,
            },
        )
        return {'status': 'succeeded', 'operation_id': OPERATION_ID}
    except JobExecutionUnavailable:
        return {'status': 'blocked', 'operation_id': OPERATION_ID}
    except Exception:
        # Never expose original Runner exceptions, paths, secrets or raw events.
        context.fail(
            'Read-only Ansible pilot failed. Inspect sanitized canonical JobExecution evidence.',
            error_code='automation_pilot_failed',
        )
        return {'status': 'failed', 'operation_id': OPERATION_ID}


@shared_task(
    name='app.infrastructure_automation.tasks.materialize_kubespray_plan_review',
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def materialize_kubespray_plan_review(
    self: Any,
    *,
    connection_id: int,
    host_preflight_job_id: int,
    job_execution_id: int,
) -> dict[str, str]:
    """Commit one read-only candidate through the canonical automation job.

    No SSH/Runner/Kubernetes API is reachable through this operation. The
    preflight source is checked again on-worker immediately before commit.
    """
    context = JobExecutionContext(task_id=str(self.request.id), job_execution_id=job_execution_id)
    try:
        context.start(message='Qualifying reviewed Kubespray Plan evidence', stage='preflight')
        if type(connection_id) is not int or type(host_preflight_job_id) is not int:
            raise ValueError('Invalid plan target')
        connection = db.session.get(IntegrationInstance, connection_id)
        host_job = db.session.get(JobExecution, host_preflight_job_id)
        if connection is None or host_job is None:
            raise ValueError('Preflight identity unavailable')
        if (
            connection.integration_type != 'configuration_automation'
            or connection.provider_key != 'ansible'
            or not connection.enabled
            or connection.lifecycle_status != 'active'
            or host_job.integration_instance_id != connection_id
        ):
            raise ValueError('Unqualified source connection')
        latest = committed_kubespray_preflight(connection)
        if latest.state != 'ready_for_review' or latest.facts_job_public_id != host_job.public_id:
            raise ValueError('Preflight was superseded or is not qualified')
        plan = build_kubespray_plan_review(connection, host_job)
        if plan.status != 'requires_independent_approval' or not plan.plan_fingerprint:
            raise ValueError('Review-only Plan has no qualified target evidence')

        context.checkpoint(message='Checking latest evidence and Plan fingerprint', stage='verification')
        latest = committed_kubespray_preflight(connection)
        rechecked = build_kubespray_plan_review(connection, host_job)
        if (
            latest.state != 'ready_for_review'
            or latest.facts_job_public_id != host_job.public_id
            or rechecked.plan_fingerprint != plan.plan_fingerprint
        ):
            raise ValueError('Plan preflight changed before evidence commit')
        fingerprint = rechecked.plan_fingerprint
        if fingerprint is None:
            raise ValueError('Verified plan fingerprint is missing')
        context.succeed(result_type=PLAN_RESULT_TYPE, result_summary=rechecked.committed_summary())
        return {'status': 'succeeded', 'plan_fingerprint': fingerprint}
    except JobCancellationRequested:
        context.canceled(message='Kubespray Plan review canceled before evidence commit.')
        return {'status': 'canceled'}
    except JobExecutionUnavailable:
        return {'status': 'blocked'}
    except Exception:
        # Never put inventory contents, Python traceback, secrets or raw input
        # into canonical job errors or Celery result.
        context.fail(
            'Kubespray Plan review blocked. Revalidate host/source evidence before retrying.',
            error_code='kubespray_plan_review_unqualified',
        )
        return {'status': 'blocked'}

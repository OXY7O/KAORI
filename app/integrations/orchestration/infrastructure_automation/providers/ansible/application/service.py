"""Canonical read-only Ansible integration instance lifecycle and dispatch (#4817).

External SSH hosts, private inventories, credentials and arbitrary playbooks are
intentionally unsupported. UI reads committed IntegrationInstance/JobExecution.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions.db import db
from app.infrastructure_automation.source import (
    OPERATION_ID,
    SOURCE_REPOSITORY,
    SOURCE_SHA,
    require_local_pilot_enabled,
    verify_localhost_source,
)
from app.infrastructure_automation.tasks import AUTOMATION_QUEUE, collect_localhost_facts
from app.integrations.orchestration.infrastructure_automation.providers.ansible import INTEGRATION_TYPE, PROVIDER_KEY
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job

_ALLOWED_FORM_FIELDS = frozenset({'csrf_token', 'name', 'description', 'environment', 'enabled'})
_ALLOWED_ENVIRONMENTS = frozenset({'development', 'testing', 'uat'})


@dataclass(frozen=True, slots=True)
class AnsibleConnectionForm:
    name: str
    description: str
    environment: str
    enabled: bool


def parse_connection_form(data: Mapping[str, Any]) -> AnsibleConnectionForm:
    """Reject all unexpected form fields, including inventory/secret injection."""
    if set(data) - _ALLOWED_FORM_FIELDS:
        raise ValueError('Only connection identity and lifecycle fields are accepted.')
    name = str(data.get('name') or '').strip()
    description = str(data.get('description') or '').strip()
    environment = str(data.get('environment') or '').strip().lower()
    if not 1 <= len(name) <= 120:
        raise ValueError('Connection name must have 1–120 characters.')
    if len(description) > 1000:
        raise ValueError('Description cannot exceed 1,000 characters.')
    if environment not in _ALLOWED_ENVIRONMENTS:
        raise ValueError('Choose a non-production environment (Development, Testing or UAT).')
    return AnsibleConnectionForm(
        name=name,
        description=description,
        environment=environment,
        enabled=str(data.get('enabled') or '').lower() in {'1', 'true', 'on'},
    )


def instance_or_none(instance_id: int) -> IntegrationInstance | None:
    return IntegrationInstance.query.filter_by(
        id=instance_id,
        integration_type=INTEGRATION_TYPE,
        provider_key=PROVIDER_KEY,
    ).first()


def save_connection(form: AnsibleConnectionForm, instance: IntegrationInstance | None = None) -> IntegrationInstance:
    """Persist through canonical IntegrationInstance, never a second provider table."""
    existing = IntegrationInstance.query.filter_by(integration_type=INTEGRATION_TYPE, name=form.name).first()
    if existing is not None and (instance is None or existing.id != instance.id):
        raise ValueError('An Ansible connection with this name already exists.')
    record = instance or IntegrationInstance(
        integration_type=INTEGRATION_TYPE,
        provider_key=PROVIDER_KEY,
        adapter_key='ansible_runner',
        name=form.name,
    )
    record.name = form.name
    record.description = form.description or None
    record.environment = form.environment
    record.enabled = form.enabled
    record.lifecycle_status = 'active'
    # A passing worker-local probe must never qualify remote Linux host readiness.
    record.readiness_status = 'validation_required'
    record.health_status = 'not_observed'
    record.last_error = None
    record.last_checked_at = None
    record.metadata_json = {
        'profile': 'ansible-localhost-pilot-v1',
        'operation': OPERATION_ID,
        'source_repository': SOURCE_REPOSITORY,
        'source_sha': SOURCE_SHA,
        'target_authority': 'worker-localhost-only',
        'remote_host_trust': 'not_verified',
        'execution_environment_attestation': 'not_verified',
    }
    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Unable to save this connection identity. Verify the unique name.') from exc
    return record


def enqueue_read_only_pilot(
    instance: IntegrationInstance, *, requested_by_user_id: int | None
) -> tuple[JobExecution, bool]:
    """Request a bounded worker-local task only, with canonical correlation."""
    if instance.integration_type != INTEGRATION_TYPE or instance.provider_key != PROVIDER_KEY:
        raise ValueError('Ansible integration identity mismatch.')
    if not instance.enabled or instance.lifecycle_status != 'active':
        raise ValueError('Enable the registered connection before requesting a local pilot.')
    if instance.environment not in _ALLOWED_ENVIRONMENTS:
        raise ValueError('This pilot is not enabled for production targets.')
    metadata = instance.metadata_json or {}
    if metadata.get('source_repository') != SOURCE_REPOSITORY or metadata.get('source_sha') != SOURCE_SHA:
        raise ValueError('Automation source identity is not approved.')
    require_local_pilot_enabled()
    source_path = str(current_app.config.get('ANSIBLE_OPERATIONS_SOURCE_PATH') or '').strip()
    if not source_path:
        raise ValueError('Operator must configure the approved automation source path on the worker.')
    root = verify_localhost_source(source_path, SOURCE_SHA)
    return enqueue_canonical_job(
        task=collect_localhost_facts,
        task_kwargs={'source_path': str(root), 'source_sha': SOURCE_SHA},
        job_type='infrastructure_automation',
        operation='automation_localhost_host_facts',
        queue_name=AUTOMATION_QUEUE,
        workload_class='validation',
        requested_by_user_id=requested_by_user_id,
        integration_type=INTEGRATION_TYPE,
        integration_instance_id=instance.id,
        resource_group=f'integration:{INTEGRATION_TYPE}:{instance.id}',
        scope_type='linux_host',
        scope_key='localhost:automation-worker',
        parameters={
            'operation_id': OPERATION_ID,
            'source_repository': SOURCE_REPOSITORY,
            'source_sha': SOURCE_SHA,
            'target': 'worker-localhost-only',
            'integration_instance_id': instance.id,
        },
        max_attempts=1,
        dispatch_options=JobDispatchOptions(
            require_registered_worker=True,
            soft_time_limit_seconds=150,
            hard_time_limit_seconds=180,
        ),
    )


def jobs_query(instance_id: int):
    return JobExecution.query.filter_by(
        integration_type=INTEGRATION_TYPE,
        integration_instance_id=instance_id,
        operation='automation_localhost_host_facts',
    ).order_by(JobExecution.created_at.desc(), JobExecution.id.desc())

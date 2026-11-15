"""Canonical source-only Ansible connection registration and read model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.common.pagination import paginate_query
from app.extensions.db import db
from app.integrations.orchestration.configuration_automation.providers.ansible.contract import (
    AnsibleConnectionInput,
    require_registration_policy,
)
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution

INTEGRATION_TYPE = 'configuration_automation'
PROVIDER_KEY = 'ansible'
ADAPTER_KEY = 'ansible_runner'


@dataclass(frozen=True, slots=True)
class AnsibleConnectionRecord:
    """A thin provider record backed by canonical IntegrationInstance identity."""

    integration_instance: IntegrationInstance

    @property
    def id(self) -> int:
        return int(self.integration_instance.id)


def get_connection(instance_id: int) -> IntegrationInstance | None:
    return db.session.get(IntegrationInstance, int(instance_id)) if instance_id > 0 and (
        (record := db.session.get(IntegrationInstance, int(instance_id))) is not None
        and record.integration_type == INTEGRATION_TYPE
        and record.provider_key == PROVIDER_KEY
    ) else None


def record_for_canonical(instance_id: int) -> AnsibleConnectionRecord | None:
    record = get_connection(instance_id)
    return AnsibleConnectionRecord(record) if record is not None else None


def save_source_connection(
    values: AnsibleConnectionInput, *, evidence: dict[str, Any]
) -> IntegrationInstance:
    """A successful Git proof never authorizes infrastructure mutation."""
    require_registration_policy(values)
    if (
        evidence.get('status') != 'source_checked'
        or evidence.get('repository') != values.repository
        or evidence.get('revision') != values.revision
        or evidence.get('operation_authorized') is not False
    ):
        raise ValueError('Source has not passed the reviewed Git validation contract.')
    if IntegrationInstance.query.filter_by(integration_type=INTEGRATION_TYPE, name=values.name).first():
        raise ValueError('An automation connection with this name already exists.')
    instance = IntegrationInstance(
        integration_type=INTEGRATION_TYPE,
        provider_key=PROVIDER_KEY,
        adapter_key=ADAPTER_KEY,
        name=values.name,
        description=values.description,
        environment=values.environment,
        enabled=False,
        lifecycle_status='active',
        readiness_status='validation_required',
        health_status=None,
        metadata_json={
            'profile_key': values.profile_key,
            'source_provider': 'github',
            'source_repository': values.repository,
            'source_sha': values.revision,
            'ansible_core_version': values.ansible_core_version,
            'ansible_runner_version': values.ansible_runner_version,
            'kubespray_release': values.kubespray_release,
            'execution_environment_digest': values.execution_environment_digest,
            'source_validation': evidence,
            'execution_enabled': False,
            'mutation_authorized': False,
            'inventory_status': 'not_collected',
        },
    )
    try:
        db.session.add(instance)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return instance


def list_connections(*, query: str = '', environment: str = '', page: int = 1, per_page: int = 5):
    statement = IntegrationInstance.query.filter_by(integration_type=INTEGRATION_TYPE, provider_key=PROVIDER_KEY)
    totals = statement.count()
    ready = statement.filter(IntegrationInstance.readiness_status == 'ready', IntegrationInstance.enabled.is_(True)).count()
    if query:
        statement = statement.filter(IntegrationInstance.name.ilike(f'%{query[:80]}%'))
    if environment:
        statement = statement.filter(IntegrationInstance.environment == environment)
    statement = statement.order_by(IntegrationInstance.name.asc(), IntegrationInstance.id.asc())
    records, pagination = paginate_query(statement, page=page, per_page=per_page)
    return records, pagination, {'total': totals, 'ready': ready, 'attention': totals - ready}


def connection_jobs(connection: IntegrationInstance, *, page: int = 1, per_page: int = 5):
    """No job without an explicit canonical connection identity can be attributed."""
    statement = JobExecution.query.filter_by(
        integration_type=INTEGRATION_TYPE,
        integration_instance_id=connection.id,
    ).order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
    return paginate_query(statement, page=page, per_page=per_page)

"""Canonical source-only Ansible connection registration and read model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.common.pagination import paginate_query
from app.extensions.db import db
from app.integrations.source_control.source_control.providers.github.public_automation_source import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    KUBESPRAY_RELEASE,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)

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
    if instance_id <= 0:
        return None
    record = db.session.get(IntegrationInstance, int(instance_id))
    if record is None or record.integration_type != INTEGRATION_TYPE or record.provider_key != PROVIDER_KEY:
        return None
    return record


def record_for_canonical(instance_id: int) -> AnsibleConnectionRecord | None:
    record = get_connection(instance_id)
    return AnsibleConnectionRecord(record) if record is not None else None


def save_source_connection(values: AnsibleConnectionInput, *, evidence: dict[str, Any]) -> IntegrationInstance:
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
    instance = IntegrationInstance()
    instance.integration_type = INTEGRATION_TYPE
    instance.provider_key = PROVIDER_KEY
    instance.adapter_key = ADAPTER_KEY
    instance.name = values.name
    instance.description = values.description
    instance.environment = values.environment
    instance.enabled = False
    instance.lifecycle_status = 'active'
    instance.readiness_status = 'validation_required'
    instance.health_status = None
    instance.metadata_json = {
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
    }
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
    ready = statement.filter(
        IntegrationInstance.readiness_status == 'ready', IntegrationInstance.enabled.is_(True)
    ).count()
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



def source_validation_posture(connection: IntegrationInstance) -> dict[str, Any]:
    """Present committed source evidence without inferring runtime readiness.

    Fail closed on missing, superseded or malformed evidence, including older
    source checks that do not match the currently committed exact version policy.
    """
    metadata = connection.metadata_json if isinstance(connection.metadata_json, dict) else {}
    evidence = metadata.get('source_validation')
    evidence = evidence if isinstance(evidence, dict) else {}
    observed = str(evidence.get('status') or '').strip()
    matches_source = (
        evidence.get('repository') == metadata.get('source_repository') == REPOSITORY
        and evidence.get('revision') == metadata.get('source_sha') == SOURCE_CANDIDATE_SHA
        and evidence.get('profile_key') == metadata.get('profile_key') == PROFILE_KEY
        and evidence.get('checked_files') == 5
        and evidence.get('operation_authorized') is False
        and metadata.get('ansible_core_version') == ANSIBLE_CORE_VERSION
        and metadata.get('ansible_runner_version') == ANSIBLE_RUNNER_VERSION
        and metadata.get('kubespray_release') == KUBESPRAY_RELEASE
    )
    checked = observed == 'source_checked' and matches_source
    blocked = observed in {'blocked', 'rejected', 'failed'} or (observed == 'source_checked' and not checked)
    source_state = 'checked' if checked else ('blocked' if blocked else 'not_checked')
    status_labels = {
        'checked': 'Source Checked',
        'blocked': 'Source Blocked',
        'not_checked': 'Not Checked',
    }
    description = {
        'checked': 'Exact reviewed Git source and version metadata match committed evidence. Execution is still disabled.',
        'blocked': 'Source validation failed or its evidence no longer matches the approved revision and version policy.',
        'not_checked': 'There is no qualifying committed Git verification evidence for this connection.',
    }
    capabilities = (
        ('Discover', 'Host inventory is not admitted'),
        ('Preflight', 'Trusted SSH and host facts are not verified'),
        ('Plan', 'No approved provider-backed infrastructure Plan'),
        ('Provision', 'No approved target, credentials or mutation authority'),
        ('Verify', 'No independent Kubernetes API read-back'),
        ('Scale', 'No approved scaling plan or cluster binding'),
        ('Upgrade', 'No supported version and change window qualification'),
        ('Node Maintenance', 'No safe cordon, drain and recovery authority'),
        ('Recovery', 'No provider-verified restoration and rollback plan'),
    )
    return {
        'source_state': source_state,
        'source_label': status_labels[source_state],
        'source_tone': 'normal' if checked else ('critical' if blocked else 'unknown'),
        'source_description': description[source_state],
        'source_checked': checked,
        'checked_files': evidence.get('checked_files') if checked else 0,
        'observed_at': evidence.get('observed_at') if checked else None,
        'toolchain_label': 'Pinned · Not Verified',
        'worker_label': 'Not Verified',
        'cluster_label': 'Not Collected',
        'capabilities': capabilities,
        'runtime_authorized': False,
        'mutation_authorized': False,
    }

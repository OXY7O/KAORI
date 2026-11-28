"""Canonical source-only Ansible connection registration and read model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.common.pagination import paginate_query
from app.extensions.db import db
from app.infrastructure_automation.kubernetes.source_policy import committed_source_state
from app.infrastructure_automation.target_claims import connection_resource, has_active_target_claim
from app.integrations.orchestration.configuration_automation.providers.ansible.contract import (
    AnsibleConnectionInput,
    require_registration_policy,
)
from app.models.automation import AutomationInventoryAssignment, AutomationRunTargetClaim
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance
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


_SOURCE_FIELDS = frozenset({
    'profile_key',
    'source_provider',
    'source_repository',
    'source_sha',
    'ansible_core_version',
    'ansible_runner_version',
    'kubespray_release',
    'execution_environment_digest',
    'source_validation',
    'execution_enabled',
    'mutation_authorized',
    'inventory_status',
    'configuration_history',
})


def source_update_scope(connection: IntegrationInstance) -> str:
    """Bind update proof to exact current identity and configuration."""
    payload = json.dumps(
        {
            'id': connection.id,
            'name': connection.name,
            'description': connection.description,
            'environment': connection.environment,
            'enabled': connection.enabled,
            'lifecycle': connection.lifecycle_status,
            'readiness': connection.readiness_status,
            'health': connection.health_status,
            'last_error': connection.last_error,
            'last_checked_at': connection.last_checked_at.isoformat() if connection.last_checked_at else None,
            'metadata': connection.metadata_json,
        },
        sort_keys=True,
        separators=(',', ':'),
    )
    return f'ansible-update:{connection.id}:' + sha256(payload.encode('utf-8')).hexdigest()


def source_update_allowed(connection: IntegrationInstance) -> bool:
    """Only an unused source-only record can activate a new revision in this slice."""
    metadata = connection.metadata_json or {}
    if (
        not isinstance(metadata, dict)
        or set(metadata) - _SOURCE_FIELDS
        or connection.enabled
        or connection.lifecycle_status != 'active'
        or connection.readiness_status not in (None, 'validation_required')
        or connection.health_status is not None
        or metadata.get('execution_enabled', False) is not False
        or metadata.get('mutation_authorized', False) is not False
        or metadata.get('inventory_status', 'not_collected') != 'not_collected'
        or not isinstance(metadata.get('configuration_history', []), list)
        or len(metadata.get('configuration_history', [])) >= 32
    ):
        return False
    return not (
        AutomationInventoryAssignment.query.filter_by(integration_instance_id=connection.id).first()
        or IntegrationBinding.query.filter_by(integration_instance_id=connection.id).first()
        or JobExecution.query.filter_by(integration_instance_id=connection.id).first()
        or AutomationRunTargetClaim.query.filter_by(active_resource_key=connection_resource(connection.id)).first()
    )


def update_source_connection(
    connection_id: int,
    values: AnsibleConnectionInput,
    *,
    evidence: dict[str, Any],
    expected_scope: str,
    user_id: int,
) -> IntegrationInstance:
    """Archive previous source and activate a newly validated unused source revision."""
    require_registration_policy(values)
    try:
        connection = db.session.get(IntegrationInstance, connection_id, with_for_update=True, populate_existing=True)
        if (
            connection is None
            or connection.integration_type != INTEGRATION_TYPE
            or connection.provider_key != PROVIDER_KEY
            or source_update_scope(connection) != expected_scope
            or has_active_target_claim(connection_resource(connection_id))
            or not source_update_allowed(connection)
        ):
            raise ValueError('Connection changed or has dependent operational evidence; update is blocked.')
        if IntegrationInstance.query.filter(
            IntegrationInstance.integration_type == INTEGRATION_TYPE,
            IntegrationInstance.name == values.name,
            IntegrationInstance.id != connection_id,
        ).first():
            raise ValueError('An automation connection with this name already exists.')
        previous = dict(connection.metadata_json or {})
        history = list(previous.pop('configuration_history', []))
        next_metadata = {
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
        if committed_source_state(next_metadata) != 'checked':
            raise ValueError('Updated source does not match reviewed evidence.')
        history.append(
            {
                'archived_at': datetime.now(UTC).isoformat(),
                'archived_by': user_id,
                'name': connection.name,
                'description': connection.description,
                'environment': connection.environment,
                'readiness': connection.readiness_status,
                'last_error': connection.last_error,
                'last_checked_at': connection.last_checked_at.isoformat() if connection.last_checked_at else None,
                'configuration': previous,
            }
        )
        connection.name = values.name
        connection.description = values.description
        connection.environment = values.environment
        connection.metadata_json = {**next_metadata, 'configuration_history': history}
        connection.enabled = False
        connection.readiness_status = 'validation_required'
        connection.health_status = None
        connection.last_error = None
        connection.last_checked_at = None
        db.session.commit()
    except (SQLAlchemyError, ValueError):
        db.session.rollback()
        raise
    return connection


class SourceRevalidationDenied(ValueError):
    """Safe rejection of a conflicting or stale source revalidation."""


def commit_source_revalidation(connection: IntegrationInstance, *, evidence: dict[str, Any]) -> None:
    """Serialize positive source evidence against reservations; never suppress invalidation."""
    try:
        previous = dict(connection.metadata_json or {})
        locked = db.session.get(IntegrationInstance, connection.id, with_for_update=True, populate_existing=True)
        if locked is None or locked.integration_type != INTEGRATION_TYPE or locked.provider_key != PROVIDER_KEY:
            raise SourceRevalidationDenied('Source revalidation requires an Ansible connection.')
        metadata = locked.metadata_json if isinstance(locked.metadata_json, dict) else {}
        if any(metadata.get(key) != previous.get(key) for key in ('source_repository', 'source_sha')):
            raise SourceRevalidationDenied('Source identity changed during validation. Revalidate the current source.')
        reserved = has_active_target_claim(connection_resource(locked.id))
        invalidation = evidence == {'status': 'blocked', 'operation_authorized': False, 'checked_files': 0}
        if not invalidation:
            if reserved:
                raise SourceRevalidationDenied('Source refresh is blocked by an active pilot target reservation.')
            if (
                metadata.get('source_validation') != previous.get('source_validation')
                or committed_source_state({**metadata, 'source_validation': evidence}) != 'checked'
            ):
                raise SourceRevalidationDenied('Source evidence changed or is no longer qualified. Revalidate the current source.')
        locked.metadata_json = {
            **metadata,
            'source_validation': evidence,
            'execution_enabled': False,
            'mutation_authorized': False,
        }
        locked.readiness_status = 'validation_required'
        locked.health_status = None
        db.session.commit()
    except (SQLAlchemyError, SourceRevalidationDenied):
        db.session.rollback()
        raise


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
    source_state = committed_source_state(metadata)
    checked = source_state == 'checked'
    status_labels = {
        'checked': 'Source Checked',
        'blocked': 'Source Blocked',
        'not_checked': 'Not Checked',
    }
    description = {
        'checked': 'Exact reviewed Git source and version metadata match committed evidence. Execution is still disabled.',
        'blocked': (
            'Source validation failed or its evidence no longer matches the approved revision and version policy. '
            'Update unused connections with fresh source validation; dependent connections require governed migration.'
        ),
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
        'source_tone': 'normal' if checked else ('critical' if source_state == 'blocked' else 'unknown'),
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


def bound_kubernetes_targets(
    connection: IntegrationInstance, *, page: int = 1, per_page: int = 5
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read a connection's canonical cluster bindings only; never infer Run authority.

    The Cluster model is authoritative for identity; Git inventory and arbitrary
    asset_key text are not accepted as an alternative target registry.
    """
    statement = IntegrationBinding.query.filter_by(
        integration_instance_id=connection.id,
        asset_type='kubernetes_cluster',
    ).order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc())
    bindings, pagination = paginate_query(statement, page=page, per_page=per_page)
    ids = {str(binding.asset_key) for binding in bindings}
    clusters = (
        {cluster.id: cluster for cluster in db.session.scalars(select(Cluster).where(Cluster.id.in_(ids))).all()}
        if ids
        else {}
    )
    rows = []
    for binding in bindings:
        cluster = clusters.get(str(binding.asset_key))
        rows.append(
            {
                'binding_id': binding.id,
                'cluster_name': cluster.name if cluster is not None else 'Cluster identity missing',
                'environment': cluster.environment if cluster is not None else None,
                'cluster_id': cluster.id if cluster is not None else None,
                'binding_enabled': bool(binding.enabled),
                'validation_status': str(binding.validation_status or 'validation_required'),
                'last_validated_at': binding.last_validated_at,
                'identity_resolved': cluster is not None,
                'execution_authorized': False,
            }
        )
    return rows, pagination

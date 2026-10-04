from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from app.artifact_registry.collectors import InventoryProgressCallback
from app.artifact_registry.eligibility import registry_inventory_eligibility
from app.extensions.db import db
from app.integrations.kernel.registry import get_integration
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryGovernanceState,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryReplicationPolicy,
)


@dataclass(slots=True)
class ProjectGovernanceRecord:
    project_name: str
    retention_status: str = 'not_collected'
    retention_policy_ref: str | None = None
    retention_summary: dict[str, Any] = field(default_factory=dict)
    immutability_status: str = 'not_collected'
    immutability_rule_count: int | None = None
    immutability_summary: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReplicationPolicyRecord:
    provider_native_id: str
    name: str
    enabled: bool | None = None
    trigger_type: str | None = None
    source_registry: str | None = None
    destination_registry: str | None = None
    destination_namespace: str | None = None
    filters: list[Any] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RegistryGovernanceEvidence:
    projects: list[ProjectGovernanceRecord] = field(default_factory=list)
    replication_policies: list[ReplicationPolicyRecord] = field(default_factory=list)
    capability_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegistryGovernanceCollector:
    provider_key: str
    collect: Callable[[Any], RegistryGovernanceEvidence]
    collect_with_progress: Callable[
        [Any, InventoryProgressCallback | None],
        RegistryGovernanceEvidence,
    ] | None = None


_COLLECTORS: dict[str, RegistryGovernanceCollector] = {}
_LOCK = RLock()


def register_registry_governance_collector(
    collector: RegistryGovernanceCollector,
    *,
    replace: bool = False,
) -> None:
    key = str(collector.provider_key or '').strip().lower()
    if not key:
        raise ValueError('Registry governance collector requires a provider_key.')
    with _LOCK:
        if key in _COLLECTORS and not replace:
            raise ValueError(f'Registry governance collector {key!r} is already registered.')
        _COLLECTORS[key] = collector


def get_registry_governance_collector(provider_key: str) -> RegistryGovernanceCollector:
    get_integration('registry')
    key = str(provider_key or '').strip().lower()
    collector = _COLLECTORS.get(key)
    if collector is None:
        raise LookupError(f'No qualified Registry governance collector is registered for provider {key!r}.')
    return collector


def registered_registry_governance_collectors() -> tuple[RegistryGovernanceCollector, ...]:
    get_integration('registry')
    return tuple(_COLLECTORS[key] for key in sorted(_COLLECTORS))


def sync_registry_governance(
    identity: IntegrationInstance,
    *,
    progress_callback: InventoryProgressCallback | None = None,
) -> dict[str, Any]:
    """Collect optional governance evidence without changing provider state."""

    if identity.integration_type != 'registry':
        raise RuntimeError('Registry governance requires a canonical Registry integration identity.')
    if not identity.enabled or identity.lifecycle_status != 'active':
        raise RuntimeError('The Registry integration is not active.')

    module = get_integration('registry')
    provider_record = module.require_record_for_canonical(int(identity.id))
    eligibility = registry_inventory_eligibility(identity, provider_record=provider_record)
    if not eligibility.eligible:
        raise RuntimeError(eligibility.reason)

    collector = get_registry_governance_collector(identity.provider_key)
    observed_at = datetime.now(UTC)
    evidence = (
        collector.collect_with_progress(provider_record, progress_callback)
        if collector.collect_with_progress is not None
        else collector.collect(provider_record)
    )

    state = db.session.get(RegistryGovernanceState, identity.id)
    if state is None:
        state = RegistryGovernanceState(integration_instance_id=identity.id)
        db.session.add(state)

    project_by_name = {
        item.name: item
        for item in RegistryProject.query.filter_by(integration_instance_id=identity.id).all()
    }
    project_ids = [project.id for project in project_by_name.values()]
    if project_ids:
        RegistryProjectGovernance.query.filter(
            RegistryProjectGovernance.project_id.in_(project_ids)
        ).delete(synchronize_session=False)

    RegistryReplicationPolicy.query.filter_by(
        integration_instance_id=identity.id
    ).delete(synchronize_session=False)
    db.session.flush()

    committed_projects = 0
    for record in evidence.projects:
        project = project_by_name.get(record.project_name)
        if project is None:
            continue
        db.session.add(
            RegistryProjectGovernance(
                project_id=project.id,
                retention_status=record.retention_status,
                retention_policy_ref=record.retention_policy_ref,
                retention_summary=record.retention_summary,
                immutability_status=record.immutability_status,
                immutability_rule_count=record.immutability_rule_count,
                immutability_summary=record.immutability_summary,
                provider_metadata=record.provider_metadata,
                observed_at=observed_at,
            )
        )
        committed_projects += 1

    for record in evidence.replication_policies:
        db.session.add(
            RegistryReplicationPolicy(
                integration_instance_id=identity.id,
                provider_native_id=record.provider_native_id,
                name=record.name,
                enabled=record.enabled,
                trigger_type=record.trigger_type,
                source_registry=record.source_registry,
                destination_registry=record.destination_registry,
                destination_namespace=record.destination_namespace,
                filters_json=record.filters,
                provider_metadata=record.provider_metadata,
                observed_at=observed_at,
            )
        )

    state.status = 'ready'
    state.capability_states = evidence.capability_states
    state.last_observed_at = observed_at
    state.last_committed_at = datetime.now(UTC)
    state.last_error = None
    state.metadata_json = {
        **evidence.provider_metadata,
        'provider_key': identity.provider_key,
    }
    db.session.commit()
    return {
        'projects': committed_projects,
        'replication_policies': len(evidence.replication_policies),
        'capability_states': evidence.capability_states,
        'observed_at': observed_at.isoformat(),
    }

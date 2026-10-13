from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.kernel.registry import get_integration
from app.integrations.registry.collectors import InventoryProgressCallback
from app.integrations.registry.eligibility import registry_inventory_eligibility
from app.integrations.registry.governance_contracts import (
    ProjectGovernanceRecord,
    RegistryGovernanceCollector,
    RegistryGovernanceEvidence,
    ReplicationPolicyRecord,
    get_registry_governance_collector,
    register_registry_governance_collector,
    registered_registry_governance_collectors,
)
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryCollectionState,
    RegistryGovernanceState,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryReplicationPolicy,
)

__all__ = [
    'ProjectGovernanceRecord',
    'RegistryGovernanceCollector',
    'RegistryGovernanceEvidence',
    'ReplicationPolicyRecord',
    'get_registry_governance_collector',
    'register_registry_governance_collector',
    'registered_registry_governance_collectors',
]


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

    inventory_state = db.session.get(RegistryCollectionState, int(identity.id))
    if inventory_state is None or inventory_state.last_committed_at is None:
        raise RuntimeError('Committed Registry inventory is required before Governance Sync.')
    inventory_committed_at = inventory_state.last_committed_at.isoformat()

    collector = get_registry_governance_collector(identity.provider_key)
    observed_at = datetime.now(UTC)
    evidence = (
        collector.collect_with_progress(provider_record, progress_callback)
        if collector.collect_with_progress is not None
        else collector.collect(provider_record)
    )

    state = db.session.get(RegistryGovernanceState, identity.id)
    if state is None:
        state = RegistryGovernanceState()
        state.integration_instance_id = identity.id
        db.session.add(state)

    project_by_name = {
        item.name: item for item in RegistryProject.query.filter_by(integration_instance_id=identity.id).all()
    }
    project_ids = [project.id for project in project_by_name.values()]
    previous_by_project_id = (
        {
            item.project_id: item
            for item in RegistryProjectGovernance.query.filter(
                RegistryProjectGovernance.project_id.in_(project_ids)
            ).all()
        }
        if project_ids
        else {}
    )
    capability_states = evidence.capability_states if isinstance(evidence.capability_states, dict) else {}
    unavailable = {
        name
        for name in ('retention', 'immutability', 'replication')
        if not isinstance(capability_states.get(name), dict)
        or capability_states[name].get('status') in {'unknown', 'unavailable'}
    }

    # Collectors may fail individual capability APIs. Retain previous records
    # for unavailable evidence rather than replacing them with invented empty
    # policy sets. A successful observed-empty replication result is different.
    if (capability_states.get('replication') or {}).get('status') == 'observed':
        RegistryReplicationPolicy.query.filter_by(integration_instance_id=identity.id).delete(synchronize_session=False)
        for record in evidence.replication_policies:
            policy = RegistryReplicationPolicy()
            policy.integration_instance_id = identity.id
            policy.provider_native_id = record.provider_native_id
            policy.name = record.name
            policy.enabled = record.enabled
            policy.trigger_type = record.trigger_type
            policy.source_registry = record.source_registry
            policy.destination_registry = record.destination_registry
            policy.destination_namespace = record.destination_namespace
            policy.filters_json = record.filters
            policy.provider_metadata = record.provider_metadata
            policy.observed_at = observed_at
            db.session.add(policy)

    committed_projects = 0
    for record in evidence.projects:
        project = project_by_name.get(record.project_name)
        if project is None:
            continue
        previous = previous_by_project_id.pop(project.id, None)
        governance = previous if previous is not None else RegistryProjectGovernance(project_id=project.id)
        if previous is None:
            db.session.add(governance)

        # Preserve earlier successfully observed dimensions individually. Their
        # observed_at remains conservative when either dimension is retained.
        retained = False
        if record.retention_status == 'unavailable' and previous is not None:
            retained = True
        else:
            governance.retention_status = record.retention_status
            governance.retention_policy_ref = record.retention_policy_ref
            governance.retention_summary = record.retention_summary

        if record.immutability_status == 'unavailable' and previous is not None:
            retained = True
        else:
            governance.immutability_status = record.immutability_status
            governance.immutability_rule_count = record.immutability_rule_count
            governance.immutability_summary = record.immutability_summary

        if not retained:
            governance.observed_at = observed_at
        governance.provider_metadata = {
            **(governance.provider_metadata or {}),
            **record.provider_metadata,
        }
        committed_projects += 1

    # Remove projects that were definitely absent from successful discovery;
    # prior evidence for project-specific API failures remains on their rows.
    for previous in previous_by_project_id.values():
        db.session.delete(previous)

    # Re-read the committed inventory generation: a concurrent Inventory Sync
    # invalidates the provider observation rather than stamping new inventory
    # provenance onto evidence collected from the previous generation.
    db.session.refresh(inventory_state, attribute_names=['last_committed_at'])
    if (
        inventory_state.last_committed_at is None
        or inventory_state.last_committed_at.isoformat() != inventory_committed_at
    ):
        raise RuntimeError('Registry Inventory changed during Governance Sync; previous evidence preserved.')
    state.status = 'partial' if unavailable else 'ready'
    state.capability_states = capability_states
    state.last_observed_at = observed_at
    state.last_committed_at = datetime.now(UTC)
    state.last_error = (
        'Governance capability evidence unavailable: ' + ', '.join(sorted(unavailable)) if unavailable else None
    )
    state.metadata_json = {
        **evidence.provider_metadata,
        'provider_key': identity.provider_key,
        'inventory_committed_at': inventory_committed_at,
    }
    db.session.commit()
    return {
        'projects': committed_projects,
        'replication_policies': (
            len(evidence.replication_policies)
            if (capability_states.get('replication') or {}).get('status') == 'observed'
            else 0
        ),
        'status': state.status,
        'capability_states': evidence.capability_states,
        'observed_at': observed_at.isoformat(),
    }

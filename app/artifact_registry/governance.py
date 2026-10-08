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
    RegistryGovernanceState,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryReplicationPolicy,
)

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
        state = RegistryGovernanceState()
        state.integration_instance_id = identity.id
        db.session.add(state)

    project_by_name = {
        item.name: item for item in RegistryProject.query.filter_by(integration_instance_id=identity.id).all()
    }
    project_ids = [project.id for project in project_by_name.values()]
    if project_ids:
        RegistryProjectGovernance.query.filter(RegistryProjectGovernance.project_id.in_(project_ids)).delete(
            synchronize_session=False
        )

    RegistryReplicationPolicy.query.filter_by(integration_instance_id=identity.id).delete(synchronize_session=False)
    db.session.flush()

    committed_projects = 0
    for record in evidence.projects:
        project = project_by_name.get(record.project_name)
        if project is None:
            continue
        governance = RegistryProjectGovernance()
        governance.project_id = project.id
        governance.retention_status = record.retention_status
        governance.retention_policy_ref = record.retention_policy_ref
        governance.retention_summary = record.retention_summary
        governance.immutability_status = record.immutability_status
        governance.immutability_rule_count = record.immutability_rule_count
        governance.immutability_summary = record.immutability_summary
        governance.provider_metadata = record.provider_metadata
        governance.observed_at = observed_at
        db.session.add(governance)
        committed_projects += 1

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

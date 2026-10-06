from __future__ import annotations

from typing import Any

from app.artifact_registry.collectors import InventoryProgressCallback
from app.artifact_registry.governance import (
    ProjectGovernanceRecord,
    RegistryGovernanceCollector,
    RegistryGovernanceEvidence,
    ReplicationPolicyRecord,
)
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.integrations.registry.providers.harbor.exceptions import HarborError, HarborResponseError
from app.models.harbor import HarborInstance


def _state(*, supported: bool, observed: bool, detail: str = '') -> dict[str, Any]:
    if not supported:
        status = 'unsupported'
    elif observed:
        status = 'observed'
    else:
        status = 'unavailable'
    return {'status': status, 'supported': supported, 'observed': observed, 'detail': detail}


def _metadata_value(raw: dict[str, Any], key: str) -> Any:
    metadata = raw.get('metadata')
    return metadata.get(key) if isinstance(metadata, dict) else None


def _retention_id(project: dict[str, Any]) -> str | None:
    value = _metadata_value(project, 'retention_id')
    return None if value in (None, '', 0, '0') else str(value)


def _endpoint_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return str(value.get('name') or value.get('url') or '').strip() or None
    return None


def _project_detail(client: Any, summary: dict[str, Any], states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    project_name = str(summary.get('name') or '').strip()
    try:
        return client.get_project(project_name_or_id=project_name)
    except HarborError as exc:
        states['retention'] = _state(
            supported=True,
            observed=False,
            detail=f'Project policy metadata unavailable: {type(exc).__name__}.',
        )
        return summary


def _retention_evidence(
    client: Any,
    project: dict[str, Any],
    states: dict[str, dict[str, Any]],
) -> tuple[str, str | None, dict[str, Any]]:
    retention_ref = _retention_id(project)
    if not retention_ref:
        return 'not_configured', None, {}
    try:
        raw = client.get_retention(retention_ref)
    except HarborResponseError as exc:
        states['retention'] = _state(
            supported=True,
            observed=False,
            detail=f'Retention evidence returned HTTP {exc.status}.',
        )
        return 'unavailable', retention_ref, {'error_status': exc.status}
    except HarborError as exc:
        states['retention'] = _state(
            supported=True,
            observed=False,
            detail='Retention evidence could not be collected.',
        )
        return 'unavailable', retention_ref, {'error_type': type(exc).__name__}
    return (
        'configured',
        retention_ref,
        {
            'id': raw.get('id'),
            'algorithm': raw.get('algorithm'),
            'rules': raw.get('rules') if isinstance(raw.get('rules'), list) else [],
            'trigger': raw.get('trigger'),
            'scope': raw.get('scope'),
        },
    )


def _immutability_evidence(
    client: Any,
    project_name: str,
    states: dict[str, dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    try:
        rules = client.list_immutability_rules(project_name_or_id=project_name)
    except HarborResponseError as exc:
        states['immutability'] = _state(
            supported=True,
            observed=False,
            detail=f'Immutability evidence returned HTTP {exc.status}.',
        )
        return 'unavailable', []
    except HarborError:
        states['immutability'] = _state(
            supported=True,
            observed=False,
            detail='Immutability evidence could not be collected.',
        )
        return 'unavailable', []
    enabled = [rule for rule in rules if bool(rule.get('disabled')) is False]
    return ('configured' if enabled else 'not_configured'), rules


def _webhook_count(client: Any, project_name: str, states: dict[str, dict[str, Any]]) -> int:
    try:
        return len(client.list_webhook_policies(project_name_or_id=project_name))
    except HarborError:
        states['webhook'] = _state(
            supported=True,
            observed=False,
            detail='Provider webhook policy evidence could not be collected.',
        )
        return 0


def _project_governance_record(
    client: Any,
    summary: dict[str, Any],
    states: dict[str, dict[str, Any]],
) -> ProjectGovernanceRecord | None:
    project_name = str(summary.get('name') or '').strip()
    if not project_name:
        return None
    project = _project_detail(client, summary, states)
    retention_status, retention_ref, retention_summary = _retention_evidence(client, project, states)
    immutability_status, immutable_rules = _immutability_evidence(client, project_name, states)
    return ProjectGovernanceRecord(
        project_name=project_name,
        retention_status=retention_status,
        retention_policy_ref=retention_ref,
        retention_summary=retention_summary,
        immutability_status=immutability_status,
        immutability_rule_count=len(immutable_rules),
        immutability_summary={'rules': immutable_rules},
        provider_metadata={'provider_webhook_policy_count': _webhook_count(client, project_name, states)},
    )


def _replication_policies(client: Any, states: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        return client.list_all_replication_policies()
    except HarborResponseError as exc:
        states['replication'] = _state(
            supported=True,
            observed=False,
            detail=f'Replication evidence returned HTTP {exc.status}.',
        )
    except HarborError:
        states['replication'] = _state(
            supported=True,
            observed=False,
            detail='Replication evidence could not be collected.',
        )
    return []


def _replication_record(policy: dict[str, Any]) -> ReplicationPolicyRecord | None:
    native_id = str(policy.get('id') or '').strip()
    if not native_id:
        return None
    trigger = policy.get('trigger')
    return ReplicationPolicyRecord(
        provider_native_id=native_id,
        name=str(policy.get('name') or f'Policy {native_id}'),
        enabled=bool(policy.get('enabled')) if policy.get('enabled') is not None else None,
        trigger_type=(str(trigger.get('type') or '').strip() or None if isinstance(trigger, dict) else None),
        source_registry=_endpoint_name(policy.get('src_registry')),
        destination_registry=_endpoint_name(policy.get('dest_registry')),
        destination_namespace=str(policy.get('dest_namespace') or '').strip() or None,
        filters=list(policy.get('filters') or []),
        provider_metadata={
            'override': policy.get('override'),
            'speed': policy.get('speed'),
            'deletion': policy.get('deletion'),
        },
    )


def collect_harbor_governance(
    instance: HarborInstance,
    progress_callback: InventoryProgressCallback | None = None,
) -> RegistryGovernanceEvidence:
    client = build_client(instance)
    states = {
        key: _state(supported=True, observed=True)
        for key in ('retention', 'immutability', 'replication', 'webhook')
    }
    if progress_callback is not None:
        progress_callback(0, 0, 'Project Discovery')
    projects = client.list_all_projects()
    total_projects = len(projects)
    if progress_callback is not None:
        progress_callback(0, total_projects, '')

    project_records: list[ProjectGovernanceRecord] = []
    for index, summary in enumerate(projects, start=1):
        record = _project_governance_record(client, summary, states)
        if record is None:
            continue
        project_records.append(record)
        if progress_callback is not None:
            progress_callback(index, total_projects, record.project_name)

    replication_records = [
        record
        for policy in _replication_policies(client, states)
        if (record := _replication_record(policy)) is not None
    ]
    return RegistryGovernanceEvidence(
        projects=project_records,
        replication_policies=replication_records,
        capability_states=states,
        provider_metadata={'source': 'harbor_api_v2'},
    )


collector = RegistryGovernanceCollector(
    provider_key='harbor',
    collect=collect_harbor_governance,
    collect_with_progress=collect_harbor_governance,
)

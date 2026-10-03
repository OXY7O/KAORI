from __future__ import annotations

from typing import Any

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
    if isinstance(metadata, dict):
        return metadata.get(key)
    return None


def _retention_id(project: dict[str, Any]) -> str | None:
    value = _metadata_value(project, 'retention_id')
    if value in (None, '', 0, '0'):
        return None
    return str(value)


def _endpoint_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return str(value.get('name') or value.get('url') or '').strip() or None
    return None


def collect_harbor_governance(instance: HarborInstance) -> RegistryGovernanceEvidence:
    client = build_client(instance)
    project_records: list[ProjectGovernanceRecord] = []
    capability_states: dict[str, dict[str, Any]] = {
        'retention': _state(supported=True, observed=True),
        'immutability': _state(supported=True, observed=True),
        'replication': _state(supported=True, observed=True),
        'webhook': _state(supported=True, observed=True),
    }
    projects = client.list_all_projects()

    for summary in projects:
        project_name = str(summary.get('name') or '').strip()
        if not project_name:
            continue
        try:
            project = client.get_project(project_name_or_id=project_name)
        except HarborError as exc:
            project = summary
            capability_states['retention'] = _state(
                supported=True,
                observed=False,
                detail=f'Project policy metadata unavailable: {type(exc).__name__}.',
            )

        retention_status = 'not_configured'
        retention_ref = _retention_id(project)
        retention_summary: dict[str, Any] = {}
        if retention_ref:
            try:
                raw_retention = client.get_retention(retention_ref)
            except HarborResponseError as exc:
                retention_status = 'unavailable'
                retention_summary = {'error_status': exc.status}
                capability_states['retention'] = _state(
                    supported=True,
                    observed=False,
                    detail=f'Retention evidence returned HTTP {exc.status}.',
                )
            except HarborError as exc:
                retention_status = 'unavailable'
                retention_summary = {'error_type': type(exc).__name__}
                capability_states['retention'] = _state(
                    supported=True,
                    observed=False,
                    detail='Retention evidence could not be collected.',
                )
            else:
                retention_status = 'configured'
                retention_summary = {
                    'id': raw_retention.get('id'),
                    'algorithm': raw_retention.get('algorithm'),
                    'rules': raw_retention.get('rules') if isinstance(raw_retention.get('rules'), list) else [],
                    'trigger': raw_retention.get('trigger'),
                    'scope': raw_retention.get('scope'),
                }

        try:
            immutable_rules = client.list_immutability_rules(project_name_or_id=project_name)
        except HarborResponseError as exc:
            immutability_status = 'unavailable'
            immutable_rules = []
            capability_states['immutability'] = _state(
                supported=True,
                observed=False,
                detail=f'Immutability evidence returned HTTP {exc.status}.',
            )
        except HarborError:
            immutability_status = 'unavailable'
            immutable_rules = []
            capability_states['immutability'] = _state(
                supported=True,
                observed=False,
                detail='Immutability evidence could not be collected.',
            )
        else:
            enabled_rules = [
                rule for rule in immutable_rules
                if bool(rule.get('disabled')) is False
            ]
            immutability_status = 'configured' if enabled_rules else 'not_configured'

        try:
            webhook_policies = client.list_webhook_policies(project_name_or_id=project_name)
        except HarborError:
            webhook_policies = []
            capability_states['webhook'] = _state(
                supported=True,
                observed=False,
                detail='Provider webhook policy evidence could not be collected.',
            )

        project_records.append(
            ProjectGovernanceRecord(
                project_name=project_name,
                retention_status=retention_status,
                retention_policy_ref=retention_ref,
                retention_summary=retention_summary,
                immutability_status=immutability_status,
                immutability_rule_count=len(immutable_rules),
                immutability_summary={'rules': immutable_rules},
                provider_metadata={
                    'provider_webhook_policy_count': len(webhook_policies),
                },
            )
        )

    replication_records: list[ReplicationPolicyRecord] = []
    try:
        replication_policies = client.list_all_replication_policies()
    except HarborResponseError as exc:
        capability_states['replication'] = _state(
            supported=True,
            observed=False,
            detail=f'Replication evidence returned HTTP {exc.status}.',
        )
        replication_policies = []
    except HarborError:
        capability_states['replication'] = _state(
            supported=True,
            observed=False,
            detail='Replication evidence could not be collected.',
        )
        replication_policies = []

    for policy in replication_policies:
        native_id = str(policy.get('id') or '').strip()
        if not native_id:
            continue
        source = policy.get('src_registry')
        destination = policy.get('dest_registry')
        trigger = policy.get('trigger')
        replication_records.append(
            ReplicationPolicyRecord(
                provider_native_id=native_id,
                name=str(policy.get('name') or f'Policy {native_id}'),
                enabled=bool(policy.get('enabled')) if policy.get('enabled') is not None else None,
                trigger_type=(
                    str(trigger.get('type') or '').strip() or None
                    if isinstance(trigger, dict)
                    else None
                ),
                source_registry=_endpoint_name(source),
                destination_registry=_endpoint_name(destination),
                destination_namespace=str(policy.get('dest_namespace') or '').strip() or None,
                filters=list(policy.get('filters') or []),
                provider_metadata={
                    'override': policy.get('override'),
                    'speed': policy.get('speed'),
                    'deletion': policy.get('deletion'),
                },
            )
        )

    return RegistryGovernanceEvidence(
        projects=project_records,
        replication_policies=replication_records,
        capability_states=capability_states,
        provider_metadata={'source': 'harbor_api_v2'},
    )


collector = RegistryGovernanceCollector(
    provider_key='harbor',
    collect=collect_harbor_governance,
)

from __future__ import annotations

from typing import Any

from app.inventory.kubernetes.resources.common import _display_boolean, format_age
from app.inventory.kubernetes.resources.pod_semantics import (
    condition_presentation,
    container_presentation,
    operational_context,
    parse_inventory_datetime,
    pod_operational_state,
    pod_ready_values,
)
from app.models import PodInventory


def _pod_container_count(pod: PodInventory) -> int:
    configuration = (pod.details or {}).get('configuration') or {}
    configured_count = configuration.get('container_count')
    if configured_count is not None:
        try:
            return int(configured_count)
        except (TypeError, ValueError):
            pass
    if pod.container_names:
        return len(pod.container_names)
    ready_values = pod_ready_values(pod.ready)
    return ready_values[1] if ready_values else 0


def _owner_chain(pod: PodInventory, details: dict[str, Any]) -> list[dict[str, str]]:
    chain = list(details.get('owner_chain') or [])
    if chain:
        return chain
    if pod.workload_type and pod.workload_name:
        chain.append({'kind': pod.workload_type, 'name': pod.workload_name})
    chain.append({'kind': 'Pod', 'name': pod.pod_name})
    return chain


def _detail_evidence_flags(details: dict[str, Any]) -> dict[str, bool]:
    configuration = details.get('configuration') or {}
    placement = details.get('placement') or {}
    return {
        'specification': bool(
            details.get(
                'specification_evidence_reported',
                configuration.get('reported', bool(configuration or placement or details.get('volumes'))),
            )
        ),
        'runtime': bool(
            details.get(
                'runtime_evidence_reported',
                bool(details.get('container_statuses')),
            )
        ),
        'conditions': bool(
            details.get(
                'condition_evidence_reported',
                bool(details.get('conditions')),
            )
        ),
    }


def _placement_context(pod: PodInventory, details: dict[str, Any], spec_reported: bool) -> dict[str, Any]:
    placement = details.get('placement') or {}
    unknown = 'Not Reported'
    selector_reported = spec_reported and 'node_selector' in placement
    tolerations_reported = spec_reported and 'tolerations' in placement
    affinity_reported = spec_reported and 'affinity_configured' in placement
    topology_reported = spec_reported and 'topology_spread_count' in placement

    node_selectors = dict(sorted((placement.get('node_selector') or {}).items())) if selector_reported else {}
    toleration_values = list(placement.get('tolerations') or []) if tolerations_reported else []
    tolerations = {f'Toleration {index + 1}': str(value) for index, value in enumerate(toleration_values)}
    topology_count = placement.get('topology_spread_count') if topology_reported else None
    affinity = placement.get('affinity_configured') if affinity_reported else None

    rows = [
        {'label': 'Node', 'value': pod.node_name or 'Not Scheduled'},
        {'label': 'Pod IP', 'value': pod.pod_ip or unknown},
        {'label': 'Host IP', 'value': details.get('host_ip') or unknown},
        {'label': 'Scheduler', 'value': (placement.get('scheduler') or unknown) if spec_reported else unknown},
        {
            'label': 'Priority Class',
            'value': (placement.get('priority_class') or unknown) if spec_reported else unknown,
        },
        {'label': 'Topology Spread', 'value': str(int(topology_count)) if topology_count is not None else unknown},
    ]
    evidence_rows = [
        {
            'label': 'Node Selector',
            'value': (
                f'{len(node_selectors)} rule' + ('s' if len(node_selectors) != 1 else '')
                if selector_reported
                else unknown
            ),
        },
        {
            'label': 'Affinity',
            'value': ('Configured' if affinity else 'Not Configured') if affinity_reported else unknown,
        },
        {
            'label': 'Tolerations',
            'value': str(len(toleration_values)) if tolerations_reported else unknown,
        },
        {
            'label': 'Topology Spread',
            'value': str(int(topology_count)) if topology_count is not None else unknown,
        },
    ]
    evidence_complete = all((selector_reported, tolerations_reported, affinity_reported, topology_reported))
    return {
        'raw': placement,
        'rows': rows,
        'evidence_rows': evidence_rows,
        'node_selectors': node_selectors,
        'toleration_entries': tolerations,
        'constraint_count': (
            len(node_selectors) + len(toleration_values) + int(bool(affinity)) + int(topology_count or 0)
            if evidence_complete
            else None
        ),
    }


def _specification_context(
    pod: PodInventory,
    details: dict[str, Any],
    spec_reported: bool,
    volumes: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    configuration = details.get('configuration') or {}
    placement = details.get('placement') or {}
    unknown = 'Not Reported'

    def value(name: str) -> str:
        if not spec_reported:
            return unknown
        raw = configuration.get(name)
        return str(raw) if raw is not None and str(raw) else unknown

    def count_value(name: str) -> int | None:
        if not spec_reported:
            return None
        raw = configuration.get(name)
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    security_reported = spec_reported and 'security_context_configured' in configuration
    security_context = configuration.get('security_context_configured') if security_reported else None
    host_network_reported = spec_reported and 'host_network' in placement
    host_network = placement.get('host_network') if host_network_reported else None
    normalized = {
        'service_account': value('service_account'),
        'restart_policy': value('restart_policy'),
        'dns_policy': value('dns_policy'),
        'runtime_class': value('runtime_class'),
        'security_context_configured': security_context,
        'image_pull_secret_count': count_value('image_pull_secret_count'),
        'volume_count': count_value('volume_count'),
        'container_count': count_value('container_count'),
        'init_container_count': count_value('init_container_count'),
        'ephemeral_container_count': count_value('ephemeral_container_count'),
    }

    def displayed_count(name: str) -> str:
        raw = normalized[name]
        return str(raw) if raw is not None else unknown

    rows = [
        {'label': 'Service Account', 'value': normalized['service_account']},
        {'label': 'Restart Policy', 'value': normalized['restart_policy']},
        {'label': 'DNS Policy', 'value': normalized['dns_policy']},
        {'label': 'QoS Class', 'value': details.get('qos_class') or unknown},
        {'label': 'Runtime Class', 'value': normalized['runtime_class']},
        {
            'label': 'Host Network',
            'value': _display_boolean(bool(host_network)) if host_network_reported else unknown,
        },
        {
            'label': 'Security Context',
            'value': ('Configured' if security_context else 'Not Configured') if security_reported else unknown,
        },
        {'label': 'Image Pull Secrets', 'value': displayed_count('image_pull_secret_count')},
        {'label': 'Volumes', 'value': displayed_count('volume_count')},
        {'label': 'Containers', 'value': displayed_count('container_count')},
        {'label': 'Init Containers', 'value': displayed_count('init_container_count')},
        {'label': 'Ephemeral Containers', 'value': displayed_count('ephemeral_container_count')},
    ]
    return normalized, rows


def _reference_rows(pod: PodInventory) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    configuration = [
        {
            'name': str(reference.get('name') or 'Not Reported'),
            'supporting_primary': str(reference.get('type') or 'Configuration'),
            'supporting_secondary': 'Referenced by Pod configuration',
            'status': None,
            'status_tone': None,
        }
        for reference in (pod.configuration_references or [])
        if isinstance(reference, dict)
    ]
    storage = [
        {
            'name': str(claim_name),
            'supporting_primary': 'PersistentVolumeClaim',
            'supporting_secondary': 'Referenced by Pod volumes',
            'status': None,
            'status_tone': None,
        }
        for claim_name in (pod.persistent_volume_claims or [])
    ]
    return configuration, storage


def _owner_resolution_review(details: dict[str, Any]) -> bool:
    resolution = details.get('owner_resolution') or {}
    direct_kind = str(resolution.get('direct_kind') or '')
    if direct_kind == 'ReplicaSet':
        return resolution.get('replica_set_lookup') not in {None, 'Collected'}
    if direct_kind == 'Job':
        return resolution.get('job_lookup') not in {None, 'Collected'}
    return False


def _presented_runtime(details: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    containers = [container_presentation(container) for container in (details.get('container_statuses') or [])]
    conditions = [condition_presentation(condition) for condition in (details.get('conditions') or [])]
    return containers, conditions


def _normalized_volumes(details: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            **volume,
            'name': str(volume.get('name') or 'Not Reported'),
            'type': str(volume.get('type') or 'Not Reported'),
            'source': str(volume.get('source') or 'Not Reported'),
            'mounted_by': list(volume.get('mounted_by') or []),
        }
        for volume in (details.get('volumes') or [])
        if isinstance(volume, dict)
    ]


def _condition_evidence_rows(conditions: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            'label': condition['type'],
            'value': condition['state_label'],
            'supporting': condition.get('reason') or 'No reason reported',
        }
        for condition in conditions
    ]


def _reference_evidence_availability(
    pod: PodInventory,
    details: dict[str, Any],
    specification_reported: bool,
    volumes: list[dict[str, Any]],
) -> tuple[bool, bool]:
    volume_reported = bool(specification_reported and details.get('volume_evidence_reported') is True)
    references_reported = bool(specification_reported and details.get('reference_evidence_reported') is True)
    return volume_reported, references_reported


def _owner_context(pod: PodInventory, details: dict[str, Any]) -> dict[str, Any]:
    has_controller = bool(pod.workload_type and pod.workload_name)
    owner_display = f'{pod.workload_type} · {pod.workload_name}' if has_controller else 'Standalone'
    return {
        'owner_type': pod.workload_type or 'Standalone',
        'owner_name': pod.workload_name or 'Not Reported',
        'owner_display': owner_display,
        'owner_chain': _owner_chain(pod, details),
        'owner_resolution': details.get('owner_resolution') or {},
        'owner_resolution_review': _owner_resolution_review(details),
    }


def _runtime_context(
    pod: PodInventory,
    details: dict[str, Any],
    runtime_reported: bool,
) -> dict[str, Any]:
    operational_state, operational_tone, state_evidence = pod_operational_state(
        pod.phase,
        pod.ready,
    )
    ready_values = pod_ready_values(pod.ready)
    restart_count = int(pod.restart_count or 0)
    ready_count, ready_total = ready_values or (0, 0)
    owner_review = _owner_resolution_review(details)
    return {
        'ready': pod.ready or 'Not Reported',
        'ready_count': ready_count,
        'ready_total': ready_total,
        'restarts': restart_count if runtime_reported else 'Not Reported',
        'restart_count': restart_count,
        'status': details.get('kubernetes_phase') or pod.phase or 'Unknown',
        'lifecycle_phase': pod.phase or 'Unknown',
        'deletion_timestamp': parse_inventory_datetime(details.get('deletion_timestamp')),
        'operational_state_label': operational_state,
        'operational_state_tone': operational_tone,
        'state_evidence': state_evidence,
        'reason': details.get('reason'),
        'message': details.get('message'),
        'qos_class': details.get('qos_class') or 'Not Reported',
        'operational_context': operational_context(
            operational_state,
            restart_count,
            runtime_reported,
            owner_review,
        ),
    }


def build_pod_detail(
    pod: PodInventory,
    cluster_name: str,
    cluster_environment: str,
) -> dict[str, Any]:
    details = pod.details or {}
    flags = _detail_evidence_flags(details)
    container_statuses, conditions = _presented_runtime(details)
    volumes = _normalized_volumes(details)
    placement = _placement_context(pod, details, flags['specification'])
    configuration, specification_rows = _specification_context(
        pod,
        details,
        flags['specification'],
        volumes,
    )
    configuration_references, storage_references = _reference_rows(pod)
    volume_reported, references_reported = _reference_evidence_availability(
        pod,
        details,
        flags['specification'],
        volumes,
    )

    result = {
        'id': pod.id,
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'namespace': pod.namespace,
        'name': pod.pod_name,
        'node': pod.node_name,
        'ip': pod.pod_ip,
        'host_ip': details.get('host_ip'),
        'uid': details.get('uid') or 'Not Reported',
        'conditions': conditions,
        'condition_evidence_reported': flags['conditions'],
        'condition_evidence_rows': _condition_evidence_rows(conditions),
        'runtime_evidence_reported': flags['runtime'],
        'specification_evidence_reported': flags['specification'],
        'placement': placement['raw'],
        'placement_rows': placement['rows'],
        'placement_constraint_count': placement['constraint_count'],
        'placement_evidence_rows': placement['evidence_rows'],
        'configuration': configuration,
        'specification_rows': specification_rows,
        'node_selectors': placement['node_selectors'],
        'toleration_entries': placement['toleration_entries'],
        'container_statuses': container_statuses,
        'volumes': volumes,
        'volume_evidence_reported': volume_reported,
        'configuration_references': configuration_references,
        'storage_references': storage_references,
        'reference_evidence_reported': references_reported,
        'labels': dict(sorted((pod.labels or {}).items())),
        'annotations': dict(sorted((details.get('annotations') or {}).items())),
        'age': format_age(pod.created_at),
        'created_at': pod.created_at,
        'collected_at': pod.collected_at,
    }
    result.update(_owner_context(pod, details))
    result.update(_runtime_context(pod, details, flags['runtime']))
    return result

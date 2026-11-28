"""Canonical local inventory/config document; never an execution envelope."""

from __future__ import annotations

import hashlib
import json
from ipaddress import IPv4Network
from typing import Any

from app.infrastructure_automation.host_registry import preview_inventory_intent
from app.infrastructure_automation.kubernetes.kubespray_preflight import (
    KUBESPRAY_COMMIT,
    KUBESPRAY_KUBERNETES_MINOR,
    KUBESPRAY_RELEASE,
)
from app.infrastructure_automation.kubernetes.source_policy import REPOSITORY, SOURCE_CANDIDATE_SHA, committed_source_state
from app.models.automation import AutomationInventoryAssignment
from app.models.integration import IntegrationInstance


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _network(value: str) -> IPv4Network:
    network = IPv4Network(value, strict=True)
    if not 8 <= network.prefixlen <= 24 or not any(
        network.subnet_of(IPv4Network(cidr)) for cidr in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')
    ):
        raise ValueError('An approved private IPv4 cluster network is required.')
    return network


def build_inventory_document(
    connection: IntegrationInstance,
    assignments: list[AutomationInventoryAssignment],
    *,
    pod_cidr: str,
    service_cidr: str,
    allow_source_only_preparation: bool = False,
) -> dict[str, Any]:
    """Build non-executable inventory; only local preparation may opt in before runtime admission."""
    metadata = connection.metadata_json
    source_only = (
        allow_source_only_preparation is True
        and connection.enabled is False
        and connection.lifecycle_status == 'active'
        and connection.readiness_status == 'validation_required'
        and isinstance(metadata, dict)
        and metadata.get('execution_enabled') is False
        and metadata.get('mutation_authorized') is False
    )
    if (
        connection.environment not in ('development', 'testing', 'laboratory', 'sandbox')
        or (connection.enabled is not True and not source_only)
    ):
        raise ValueError('A disposable non-production Ansible connection is required.')
    if committed_source_state(connection.metadata_json) != 'checked':
        raise ValueError('The exact reviewed Kubespray source is required.')
    preview = preview_inventory_intent(connection, assignments)
    if preview.inventory_fingerprint is None or preview.host_count != 3:
        raise ValueError('A qualified three-host inventory intent is required.')
    pod, service = _network(pod_cidr), _network(service_cidr)
    if pod.overlaps(service):
        raise ValueError('Cluster network intent overlaps.')
    hosts = [
        {
            'asset_id': assignment.host.id,
            'name': assignment.host.name,
            'address': assignment.host.address,
            'ssh_port': assignment.host.ssh_port,
            'role': assignment.role,
        }
        for assignment in sorted(assignments, key=lambda item: item.host_id)
    ]
    if (
        sum(host['role'] == 'control_plane' for host in hosts) != 1
        or sum(host['role'] == 'worker' for host in hosts) != 2
        or len({host['name'] for host in hosts}) != 3
        or len({host['address'] for host in hosts}) != 3
        or any(
            IPv4Network(f"{host['address']}/32").overlaps(network)
            for host in hosts
            for network in (pod, service)
        )
    ):
        raise ValueError('The fixed pilot topology or network intent is unqualified.')
    return {
        'schema': 'kaori.kubespray.inventory_config.v1',
        'connection_id': connection.id,
        'environment': connection.environment,
        'source_repository': REPOSITORY,
        'source_sha': SOURCE_CANDIDATE_SHA,
        'kubespray_release': KUBESPRAY_RELEASE,
        'kubespray_commit': KUBESPRAY_COMMIT,
        'kubernetes_minor': KUBESPRAY_KUBERNETES_MINOR,
        'host_registry_fingerprint': preview.inventory_fingerprint,
        'hosts': hosts,
        'config': {'pod_cidr': str(pod), 'service_cidr': str(service)},
        'execution_authorized': False,
    }

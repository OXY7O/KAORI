"""Bounded, non-mutating Kubespray pilot Plan preflight (#4800).

This module does not retrieve credentials, contact hosts, or authorize a Run.
A valid static specification always requires trusted provider read-back,
approved inventory, source/EE digest and independent human governance.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

KUBESPRAY_REPOSITORY = 'kubernetes-sigs/kubespray'
KUBESPRAY_RELEASE = 'v2.32.0'
KUBESPRAY_COMMIT = '9751ea6f63244e433a7a6263d9ecf381e57bb8e9'
KUBESPRAY_KUBERNETES_MINOR = '1.36'
KUBESPRAY_ANSIBLE_PACKAGE = '12.3.0'
SUPPORTED_OPERATING_SYSTEMS = frozenset({('Ubuntu', '24.04'), ('OracleLinux', '9')})
_REQUIRED_EVIDENCE = (
    'authorized_asset_identity',
    'verified_inventory_provenance',
    'trusted_ssh_host_key_and_reachability',
    'privileged_execution_identity',
    'host_facts_and_os_compatibility',
    'node_clock_dns_network_and_ports',
    'cluster_network_non_overlap_provider_readback',
    'capacity_and_backup_recovery_owner',
    'approved_git_revision_and_ee_digest',
    'human_risk_approval_and_maintenance_window',
)


@dataclass(frozen=True, slots=True)
class StaticKubesprayPlan:
    """Review-only assessment; never an executable or approved Plan."""

    status: str
    findings: tuple[str, ...]
    profile: str
    inventory_fingerprint: str | None
    required_evidence: tuple[str, ...]
    mutation_authorized: bool = False


def _cidr(value: object, name: str, findings: list[str]):
    if not isinstance(value, str):
        findings.append(f'{name.upper()}_INVALID')
        return None
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError:
        findings.append(f'{name.upper()}_INVALID')
        return None
    if not isinstance(network, ipaddress.IPv4Network) or not network.is_private:
        findings.append(f'{name.upper()}_MUST_BE_PRIVATE_IPV4')
        return None
    if network.prefixlen < 8 or network.prefixlen > 24:
        findings.append(f'{name.upper()}_PREFIX_UNSUPPORTED')
        return None
    return network


def assess_static_kubespray_pilot(spec: Mapping[str, Any]) -> StaticKubesprayPlan:
    """Inspect only a synthetic/authorized spec; never contact a provider.

    Findings are machine-readable codes and intentionally omit hostnames,
    IPs, secret values or other raw operator inputs.
    """
    findings: list[str] = []
    allowed = {
        'management', 'environment', 'kubespray_commit',
        'kubespray_release', 'kubernetes_minor',
        'pod_cidr', 'service_cidr', 'nodes',
    }
    if set(spec) - allowed:
        findings.append('UNRECOGNIZED_OR_SENSITIVE_INPUT')
    if spec.get('management') != 'self_managed':
        findings.append('UNSUPPORTED_MANAGED_KUBERNETES')
    environment = spec.get('environment')
    if not isinstance(environment, str) or environment not in {'development', 'nonproduction', 'uat'}:
        findings.append('NON_PRODUCTION_ONLY')
    if spec.get('kubespray_release') != KUBESPRAY_RELEASE:
        findings.append('KUBESPRAY_RELEASE_MISMATCH')
    if spec.get('kubespray_commit') != KUBESPRAY_COMMIT:
        findings.append('KUBESPRAY_SHA_MISMATCH')
    if spec.get('kubernetes_minor') != KUBESPRAY_KUBERNETES_MINOR:
        findings.append('KUBERNETES_MINOR_UNQUALIFIED')
    pod = _cidr(spec.get('pod_cidr'), 'pod_cidr', findings)
    service = _cidr(spec.get('service_cidr'), 'service_cidr', findings)
    if pod is not None and service is not None and pod.overlaps(service):
        findings.append('POD_SERVICE_NETWORK_OVERLAP')

    nodes = spec.get('nodes')
    identity_material: list[tuple[str, str, str]] = []
    if not isinstance(nodes, list) or len(nodes) != 3:
        findings.append('PILOT_TOPOLOGY_REQUIRES_THREE_NODES')
    else:
        counts = {'control_plane': 0, 'worker': 0}
        seen: set[str] = set()
        addresses: set[str] = set()
        for node in nodes:
            if not isinstance(node, dict) or set(node) != {
                'asset_id', 'role', 'os_distribution', 'os_version',
                'cpu_count', 'memory_mib', 'disk_gib', 'address',
            }:
                findings.append('NODE_SCHEMA_INVALID')
                continue
            identity = node['asset_id']
            role = node['role']
            if not isinstance(identity, str) or not identity or len(identity) > 96:
                findings.append('NODE_ASSET_ID_INVALID')
                continue
            if identity in seen:
                findings.append('DUPLICATE_NODE_ASSET')
            seen.add(identity)
            if not isinstance(role, str) or role not in counts:
                findings.append('NODE_ROLE_UNSUPPORTED')
            else:
                counts[role] += 1
            distribution = node['os_distribution']
            os_version = node['os_version']
            if (
                not isinstance(distribution, str)
                or not isinstance(os_version, str)
                or (distribution, os_version) not in SUPPORTED_OPERATING_SYSTEMS
            ):
                findings.append('NODE_OS_UNQUALIFIED')
            for field, minimum in (('cpu_count', 2), ('memory_mib', 4096), ('disk_gib', 40)):
                amount = node[field]
                if type(amount) is not int or amount < minimum:
                    findings.append('NODE_RESOURCES_BELOW_PILOT_MINIMUM')
                    break
            address = node['address']
            try:
                ip = ipaddress.IPv4Address(address) if isinstance(address, str) else None
            except ipaddress.AddressValueError:
                ip = None
            if ip is None or not (ip.is_private or ip.is_reserved):
                findings.append('NODE_ADDRESS_UNQUALIFIED')
                continue
            if address in addresses:
                findings.append('DUPLICATE_NODE_ADDRESS')
            addresses.add(address)
            if (pod is not None and ip in pod) or (service is not None and ip in service):
                findings.append('NODE_ADDRESS_OVERLAPS_CLUSTER_CIDR')
            identity_material.append((identity, role if isinstance(role, str) else '', str(ip)))
        if counts != {'control_plane': 1, 'worker': 2}:
            findings.append('PILOT_REQUIRES_ONE_CONTROL_PLANE_TWO_WORKERS')

    # Fingerprint is a correlation hint, not a signed target/approval authority.
    digest = None
    if not findings:
        material = {
            'profile': KUBESPRAY_COMMIT,
            'nodes': sorted(identity_material),
            'pod': str(pod),
            'service': str(service),
        }
        digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode('utf-8')).hexdigest()
    return StaticKubesprayPlan(
        status='blocked' if findings else 'requires_provider_evidence',
        findings=tuple(sorted(set(findings))),
        profile=f'{KUBESPRAY_REPOSITORY}@{KUBESPRAY_COMMIT}',
        inventory_fingerprint=digest,
        required_evidence=_REQUIRED_EVIDENCE,
    )

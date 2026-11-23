"""Non-mutating Kubernetes host inventory review contract (#5155).

KAORI owns host identity and inventory intent. Ansible consumes only an
independently admitted, frozen inventory at execution time. The hash below is
a correlation fingerprint, NEVER a credential, signature, or Run authorization.

This pure review boundary deliberately does not read forms, execute SSH,
resolve secret values, write an inventory file or dispatch a worker.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Any

_ALLOWED_ENVIRONMENTS = frozenset(
    {'development', 'testing', 'staging', 'laboratory', 'sandbox', 'proof_of_concept', 'non_production'}
)
_PRIVATE_NETWORKS = tuple(IPv4Network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
_REFERENCE = re.compile(r'[A-Za-z][A-Za-z0-9._:/-]{2,191}\Z')
_ASSET = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z')
_SOURCE = re.compile(r'[a-f0-9]{40}\Z')
_EE = re.compile(r'sha256:[a-f0-9]{64}\Z')


@dataclass(frozen=True, slots=True)
class InventoryHostIntent:
    """Canonical host intent input; constructed ONLY from authorized KAORI asset records.

    Credential and SSH host-key fields are *opaque references*, not secrets
    or evidence that credentials/trust were independently verified.
    """

    asset_id: str
    address: str
    ssh_port: int
    role: str
    credential_reference: str
    ssh_host_key_reference: str


@dataclass(frozen=True, slots=True)
class InventoryReviewSnapshot:
    """A sanitized fingerprint for Plan review, not an executable inventory."""

    status: str
    reason_code: str
    fingerprint: str | None
    host_count: int
    control_plane_count: int
    worker_count: int
    execution_authorized: bool = False

    def committed_summary(self) -> dict[str, Any]:
        """Never persist host addresses, SSH references, or secret material here."""
        return {
            'schema_version': 1,
            'status': self.status,
            'reason_code': self.reason_code,
            'fingerprint': self.fingerprint,
            'host_count': self.host_count,
            'control_plane_count': self.control_plane_count,
            'worker_count': self.worker_count,
            'execution_authorized': False,
        }


def _blocked(code: str) -> InventoryReviewSnapshot:
    return InventoryReviewSnapshot('blocked', code, None, 0, 0, 0)


def _private_ipv4(value: object) -> str | None:
    if type(value) is not str or value.strip() != value:
        return None
    try:
        address = IPv4Address(value)
    except ValueError:
        return None
    if not any(address in network for network in _PRIVATE_NETWORKS):
        return None
    return str(address) if str(address) == value else None


def build_kubespray_inventory_review(
    *,
    connection_id: int,
    environment: str,
    source_sha: str,
    execution_environment_digest: str,
    hosts: tuple[InventoryHostIntent, ...],
) -> InventoryReviewSnapshot:
    """Validate approved-intent SHAPE; independently admit records before use.

    Accepted candidates remain review-only, regardless of input contents.
    The caller must obtain these records from canonical KAORI persistence,
    not browser JSON or submitted Ansible inventory/YAML.
    """
    if type(connection_id) is not int or connection_id <= 0:
        return _blocked('CONNECTION_ID_UNQUALIFIED')
    if type(environment) is not str or environment not in _ALLOWED_ENVIRONMENTS:
        return _blocked('NON_PRODUCTION_ONLY')
    if type(source_sha) is not str or _SOURCE.fullmatch(source_sha) is None:
        return _blocked('SOURCE_REVISION_UNQUALIFIED')
    if type(execution_environment_digest) is not str or _EE.fullmatch(execution_environment_digest) is None:
        return _blocked('EXECUTION_ENVIRONMENT_UNQUALIFIED')
    if type(hosts) is not tuple or len(hosts) != 3:
        return _blocked('PILOT_TOPOLOGY_UNQUALIFIED')

    identities: set[str] = set()
    addresses: set[str] = set()
    counts = {'control_plane': 0, 'worker': 0}
    frozen_hosts: list[dict[str, str | int]] = []
    for host in hosts:
        if type(host) is not InventoryHostIntent:
            return _blocked('HOST_RECORD_UNQUALIFIED')
        if type(host.asset_id) is not str or _ASSET.fullmatch(host.asset_id) is None:
            return _blocked('HOST_IDENTITY_UNQUALIFIED')
        address = _private_ipv4(host.address)
        if address is None or type(host.ssh_port) is not int or not 1 <= host.ssh_port <= 65535:
            return _blocked('HOST_ENDPOINT_UNQUALIFIED')
        if host.asset_id in identities or address in addresses:
            return _blocked('DUPLICATE_HOST_IDENTITY')
        if type(host.role) is not str or host.role not in counts:
            return _blocked('HOST_ROLE_UNQUALIFIED')
        if any(
            type(reference) is not str or _REFERENCE.fullmatch(reference) is None
            for reference in (host.credential_reference, host.ssh_host_key_reference)
        ):
            return _blocked('HOST_ACCESS_REFERENCE_UNQUALIFIED')
        identities.add(host.asset_id)
        addresses.add(address)
        counts[host.role] += 1
        frozen_hosts.append(
            {
                'asset_id': host.asset_id,
                'address': address,
                'ssh_port': host.ssh_port,
                'role': host.role,
                'credential_reference': host.credential_reference,
                'ssh_host_key_reference': host.ssh_host_key_reference,
            }
        )

    if counts != {'control_plane': 1, 'worker': 2}:
        return _blocked('PILOT_TOPOLOGY_UNQUALIFIED')

    identity_material = {
        'schema_version': 1,
        'connection_id': connection_id,
        'environment': environment,
        'source_sha': source_sha,
        'execution_environment_digest': execution_environment_digest,
        'hosts': sorted(frozen_hosts, key=lambda item: str(item['asset_id'])),
    }
    fingerprint = hashlib.sha256(
        json.dumps(identity_material, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    return InventoryReviewSnapshot('review_only', 'INDEPENDENT_ADMISSION_REQUIRED', fingerprint, 3, 1, 2)

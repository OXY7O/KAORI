"""Authorized source-only Linux host intent for the first Ansible profile (#5161).

No SSH transport, secrets, Ansible inventories, mutation or Kubernetes provider
calls run from this module. Host identity and connection assignment are
distinct from NodeInventory/Kubernetes API facts.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.infrastructure_automation.target_claims import (
    connection_resource,
    endpoint_resource,
    has_active_target_claim,
    host_resource,
)
from app.models.automation import AutomationHostAsset, AutomationInventoryAssignment
from app.models.integration import IntegrationInstance

_VALID_HOSTNAME = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,94}[a-z0-9])?\Z')
_ALLOWED_ENVIRONMENTS = frozenset(
    {'development', 'staging', 'testing', 'laboratory', 'sandbox', 'proof_of_concept', 'non_production'}
)
_PRIVATE_NETWORKS = tuple(IPv4Network(cidr) for cidr in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
_ROLES = frozenset({'control_plane', 'worker'})


class AutomationInventoryDenied(ValueError):
    """Host/connection registration is not eligible for inventory intent."""


@dataclass(frozen=True, slots=True)
class AutomationHostIntent:
    name: str
    environment: str
    address: str
    ssh_port: int = 22


@dataclass(frozen=True, slots=True)
class AutomationInventoryPreview:
    connection_id: int
    state: str
    host_count: int
    inventory_fingerprint: str | None
    reason: str
    execution_authorized: bool = False

    def presentation(self) -> dict[str, Any]:
        return asdict(self)


def validate_host_intent(values: AutomationHostIntent) -> AutomationHostIntent:
    """Accept a bounded RFC1918 existing-host identity, never a target URL."""
    if type(values.name) is not str or not _VALID_HOSTNAME.fullmatch(values.name):
        raise AutomationInventoryDenied('Host name must be a canonical lowercase DNS label.')
    if values.environment not in _ALLOWED_ENVIRONMENTS:
        raise AutomationInventoryDenied('Only explicitly qualified non-production hosts are supported.')
    try:
        ip = IPv4Address(values.address)
    except (ValueError, TypeError) as exc:
        raise AutomationInventoryDenied('An existing-host IPv4 identity is required.') from exc
    if not any(ip in network for network in _PRIVATE_NETWORKS):
        raise AutomationInventoryDenied('Host address must belong to an approved RFC1918 network.')
    if type(values.ssh_port) is not int or not 1 <= values.ssh_port <= 65535:
        raise AutomationInventoryDenied('SSH port must be a valid explicit integer.')
    return AutomationHostIntent(values.name, values.environment, str(ip), values.ssh_port)


def require_ansible_connection(connection: IntegrationInstance, *, environment: str) -> None:
    if (
        connection.integration_type != 'configuration_automation'
        or connection.provider_key != 'ansible'
        or connection.environment != environment
        or connection.lifecycle_status != 'active'
        or environment not in _ALLOWED_ENVIRONMENTS
    ):
        raise AutomationInventoryDenied('An active matching non-production Ansible connection is required.')


def require_unreserved_inventory(*keys: str) -> None:
    """Reject inventory edits while persistent pilot target exclusions exist."""
    if has_active_target_claim(*keys):
        db.session.rollback()
        raise AutomationInventoryDenied('A pilot target reservation exists. Release it before changing inventory.')


def register_host_asset(values: AutomationHostIntent) -> AutomationHostAsset:
    """Persist identity only; existence of a record never authorizes SSH."""
    intent = validate_host_intent(values)
    require_unreserved_inventory(endpoint_resource(intent.address))
    record = AutomationHostAsset()
    record.name = intent.name
    record.environment = intent.environment
    record.address = intent.address
    record.ssh_port = intent.ssh_port
    record.lifecycle_status = 'registered'
    try:
        db.session.add(record)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return record


def assign_host_to_ansible(
    connection: IntegrationInstance,
    host: AutomationHostAsset,
    *,
    role: str,
) -> AutomationInventoryAssignment:
    """Scope the host to an existing Ansible connection, no implicit execution."""
    require_ansible_connection(connection, environment=host.environment)
    if role not in _ROLES or host.lifecycle_status != 'registered':
        raise AutomationInventoryDenied('Only active, supported host roles may be assigned.')
    db.session.refresh(connection, with_for_update=True)
    db.session.refresh(host, with_for_update=True)
    require_ansible_connection(connection, environment=host.environment)
    if host.lifecycle_status != 'registered':
        raise AutomationInventoryDenied('Only active, supported host roles may be assigned.')
    require_unreserved_inventory(
        connection_resource(connection.id), host_resource(host.id), endpoint_resource(host.address)
    )
    record = AutomationInventoryAssignment()
    record.integration_instance_id = connection.id
    record.host_id = host.id
    record.role = role
    record.enabled = True
    try:
        db.session.add(record)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return record


def preview_inventory_intent(
    connection: IntegrationInstance,
    assignments: list[AutomationInventoryAssignment],
) -> AutomationInventoryPreview:
    """Derive a deterministic correlation hash, never Ansible's runnable inventory.

    Fingerprints are neither signatures nor approval/credential credentials.
    An absent, duplicate, disabled or cross-scope host fails closed.
    """
    environment = connection.environment
    if not isinstance(environment, str) or environment not in _ALLOWED_ENVIRONMENTS:
        return AutomationInventoryPreview(connection.id, 'blocked', 0, None, 'Non-production scope is required.')
    try:
        require_ansible_connection(connection, environment=environment)
    except AutomationInventoryDenied:
        return AutomationInventoryPreview(connection.id, 'blocked', 0, None, 'Ansible scope is not qualified.')
    ordered: list[dict[str, object]] = []
    seen: set[str] = set()
    for assignment in assignments:
        host = assignment.host
        if (
            assignment.integration_instance_id != connection.id
            or not assignment.enabled
            or host is None
            or host.id in seen
            or host.lifecycle_status != 'registered'
            or host.environment != connection.environment
            or assignment.role not in _ROLES
        ):
            return AutomationInventoryPreview(connection.id, 'blocked', 0, None, 'Inventory identity is unqualified.')
        try:
            intent = validate_host_intent(
                AutomationHostIntent(host.name, host.environment, host.address, host.ssh_port)
            )
        except AutomationInventoryDenied:
            return AutomationInventoryPreview(connection.id, 'blocked', 0, None, 'Host endpoint is unqualified.')
        seen.add(host.id)
        ordered.append(
            {
                'host_id': host.id,
                'name': intent.name,
                'role': assignment.role,
                'address': intent.address,
                'ssh_port': intent.ssh_port,
                'environment': intent.environment,
            }
        )
    if not ordered or len(ordered) > 256:
        return AutomationInventoryPreview(connection.id, 'blocked', 0, None, 'No bounded host inventory is qualified.')
    digest = hashlib.sha256(
        json.dumps(
            {'connection_id': connection.id, 'hosts': sorted(ordered, key=lambda item: str(item['host_id']))},
            separators=(',', ':'),
            sort_keys=True,
        ).encode('utf-8')
    ).hexdigest()
    return AutomationInventoryPreview(
        connection_id=connection.id,
        state='requires_trust_admission',
        host_count=len(ordered),
        inventory_fingerprint=digest,
        reason='Inventory intent recorded. Credential, SSH host-key, worker and Plan admission remain blocked.',
    )

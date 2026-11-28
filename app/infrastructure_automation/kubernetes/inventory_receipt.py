"""Committed Kubespray KV v2 inventory receipt review; never Run authority.

Normal reads compare KAORI-owned source/host intent and a historical provider
readback receipt. No provider request, token hydration, SSH or execution.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import defer, joinedload

from app.extensions.db import db
from app.infrastructure_automation.kubernetes.inventory_document import build_inventory_document, digest
from app.infrastructure_automation.kubernetes.inventory_kv import InventoryStoreReference, stored_document
from app.infrastructure_automation.kubernetes.source_policy import ANSIBLE_CORE_VERSION
from app.integrations.secrets_management.secrets_pki.providers.openbao.service import local_provider_enabled
from app.models.automation import AutomationInventoryAssignment
from app.models.integration import IntegrationInstance
from app.models.openbao import OpenBaoInstance
from app.models.vault import VaultInstance


@dataclass(frozen=True, slots=True)
class InventoryReceiptReview:
    state: str
    description: str
    provider_label: str | None = None
    fingerprint: str | None = None
    observed_at: str | None = None
    parser_verified: bool = False
    execution_authorized: bool = False

    def presentation(self) -> dict[str, Any]:
        return asdict(self)


def _blocked(state: str, description: str) -> InventoryReceiptReview:
    return InventoryReceiptReview(state, description)


def _provider_origin(provider: IntegrationInstance, receipt: dict[str, Any]) -> str | None:
    """Use exact provider record without loading AppRole or secret material."""
    if (
        provider.integration_type != 'secrets_pki'
        or not provider.enabled
        or provider.lifecycle_status != 'active'
        or provider.provider_key != receipt.get('provider_key')
    ):
        return None
    if provider.provider_key == 'openbao' and provider.adapter_key == 'openbao_http_v1':
        if not local_provider_enabled():
            return None
        row = OpenBaoInstance.query.options(defer(OpenBaoInstance.secret_id)).filter_by(
            integration_instance_id=provider.id
        ).one_or_none()
        if row is None or row.cluster_id != receipt.get('cluster_id'):
            return None
        return str(row.endpoint)
    if provider.provider_key == 'vault' and provider.adapter_key == 'vault_http_v1':
        row = VaultInstance.query.options(defer(VaultInstance.secret_id)).filter_by(
            integration_instance_id=provider.id
        ).one_or_none()
        if (
            row is None or not row.verify_ssl or row.namespace
            or receipt.get('mount') not in (row.kv2_mounts or ())
        ):
            return None
        return str(row.endpoint)
    return None


def _qualified_receipt_shape(receipt: dict[str, Any], connection_id: int) -> bool:
    return (
        type(connection_id) is int and connection_id > 0
        and type(receipt.get('schema_version')) is int and receipt['schema_version'] == 1
        and type(receipt.get('version')) is int and receipt['version'] == 1
        and receipt.get('execution_authorized') is False
        and type(receipt.get('provider_id')) is int and receipt['provider_id'] > 0
        and receipt.get('provider_key') in ('openbao', 'vault')
        and receipt.get('ansible_inventory_parser') in ('verified', 'not_checked')
        and (
            receipt.get('ansible_inventory_parser') == 'not_checked'
            or receipt.get('ansible_core_version') == ANSIBLE_CORE_VERSION
        )
        and type(receipt.get('fingerprint')) is str and len(receipt['fingerprint']) == 64
        and all(c in '0123456789abcdef' for c in receipt['fingerprint'])
    )


def _source_matches(receipt: dict[str, Any], inventory: dict[str, Any], connection_id: int) -> bool:
    config = inventory.get('config')
    return (
        isinstance(config, dict)
        and inventory.get('connection_id') == connection_id
        and receipt.get('host_registry_fingerprint') == inventory.get('host_registry_fingerprint')
        and receipt.get('source_sha') == inventory.get('source_sha')
        and receipt.get('source_repository') == inventory.get('source_repository')
        and receipt.get('pod_cidr') == config.get('pod_cidr')
        and receipt.get('service_cidr') == config.get('service_cidr')
    )


def _observed_qualified(value: object, now: datetime | None) -> bool:
    if type(value) is not str:
        return False
    try:
        observed = datetime.fromisoformat(value)
    except ValueError:
        return False
    timestamp = now if now is not None else datetime.now(UTC)
    return observed.tzinfo is not None and timestamp.tzinfo is not None and observed <= timestamp


def review_inventory_receipt(
    receipt: object, *, connection_id: int, inventory: dict[str, Any] | None,
    provider_id: int | None, provider_key: str | None, endpoint: str | None,
    now: datetime | None = None,
) -> InventoryReceiptReview:
    """Check historical source alignment, never remote provider currentness or Run."""
    if receipt is None:
        return _blocked('not_recorded', 'No provider KV v2 inventory readback is recorded.')
    if not isinstance(receipt, dict) or not _qualified_receipt_shape(receipt, connection_id):
        return _blocked('unqualified', 'Stored inventory evidence must be requalified.')
    if (
        provider_id != receipt['provider_id'] or provider_key != receipt['provider_key']
        or not isinstance(endpoint, str) or not endpoint
        or hashlib.sha256(endpoint.encode('utf-8')).hexdigest() != receipt.get('provider_origin_sha256')
    ):
        return _blocked('provider_changed', 'Registered provider identity or origin changed; recheck KV v2.')
    if not _observed_qualified(receipt.get('observed_at'), now):
        return _blocked('unqualified', 'Stored inventory observation time is invalid.')
    if inventory is None or not _source_matches(receipt, inventory, connection_id):
        return _blocked('source_changed', 'Current source, network or host intent changed; recheck KV v2.')
    reference = InventoryStoreReference(
        receipt['provider_id'], receipt['provider_key'], str(receipt.get('cluster_id') or ''),
        str(receipt.get('mount') or ''), connection_id, receipt['fingerprint'],
    )
    if (
        not reference.cluster_id or not reference.mount
        or digest(stored_document(reference, inventory)) != reference.fingerprint
    ):
        return _blocked('source_changed', 'Provider inventory document no longer matches the recorded readback.')
    provider_label = 'OpenBao' if provider_key == 'openbao' else 'HashiCorp Vault'
    if receipt['ansible_inventory_parser'] != 'verified':
        return InventoryReceiptReview(
            'parser_unchecked', 'Stored readback aligns with committed intent; native Ansible parser check is pending.',
            provider_label=provider_label, fingerprint=reference.fingerprint, observed_at=receipt['observed_at'],
        )
    return InventoryReceiptReview(
        'historical_aligned',
        'Last provider readback and Ansible parser matched this committed intent. Remote currentness and Run trust remain unverified.',
        provider_label=provider_label, fingerprint=reference.fingerprint, observed_at=receipt['observed_at'],
        parser_verified=True,
    )


def committed_inventory_receipt_review(connection: IntegrationInstance) -> InventoryReceiptReview:
    """Bounded committed-state projection for an inventory-authorized operator."""
    metadata = connection.metadata_json if type(connection.metadata_json) is dict else {}
    receipt = metadata.get('local_inventory_store_receipt')
    if receipt is None:
        return review_inventory_receipt(
            None, connection_id=connection.id, inventory=None, provider_id=None, provider_key=None, endpoint=None,
        )
    if not isinstance(receipt, dict) or type(receipt.get('provider_id')) is not int:
        return _blocked('unqualified', 'Stored inventory evidence must be requalified.')
    provider = db.session.get(IntegrationInstance, receipt['provider_id'])
    if provider is None:
        return _blocked('provider_changed', 'Registered provider identity is unavailable.')
    endpoint = _provider_origin(provider, receipt)
    if endpoint is None:
        return _blocked('provider_changed', 'Registered provider scope is no longer qualified.')
    try:
        assignments = (
            AutomationInventoryAssignment.query.options(joinedload(AutomationInventoryAssignment.host))
            .filter_by(integration_instance_id=connection.id, enabled=True)
            .order_by(AutomationInventoryAssignment.id.asc())
            .limit(257)
            .all()
        )
        inventory = build_inventory_document(
            connection, assignments, pod_cidr=receipt.get('pod_cidr'), service_cidr=receipt.get('service_cidr'),
            allow_source_only_preparation=True,
        )
    except (ValueError, TypeError, KeyError):
        inventory = None
    return review_inventory_receipt(
        receipt, connection_id=connection.id, inventory=inventory, provider_id=provider.id,
        provider_key=provider.provider_key, endpoint=endpoint,
    )

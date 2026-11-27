"""Exact create-only local inventory document transport for Vault/OpenBao."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.infrastructure_automation.kubernetes.inventory_document import canonical_bytes, digest
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPTransport, SecretProviderError


@dataclass(frozen=True, slots=True)
class InventoryStoreReference:
    provider_id: int
    provider_key: str
    cluster_id: str
    mount: str
    connection_id: int
    fingerprint: str

    @property
    def path(self) -> str:
        return f'/v1/{self.mount}/data/kubespray/connection-{self.connection_id}/{self.fingerprint}'


def stored_document(reference: InventoryStoreReference, inventory: dict[str, Any]) -> dict[str, Any]:
    return {
        'schema': 'kaori.provider.inventory_config.v1',
        'provider_id': reference.provider_id,
        'provider_key': reference.provider_key,
        'cluster_id': reference.cluster_id,
        'mount': reference.mount,
        'inventory': inventory,
    }


def _exact_readback(body: dict[str, Any], expected: dict[str, Any]) -> bool:
    outer = body.get('data')
    if not isinstance(outer, dict):
        return False
    metadata, data = outer.get('metadata'), outer.get('data')
    return (
        isinstance(metadata, dict)
        and type(metadata.get('version')) is int
        and metadata['version'] == 1
        and metadata.get('destroyed') is False
        and metadata.get('deletion_time') == ''
        and isinstance(data, dict)
        and set(data) == {'document'}
        and isinstance(data['document'], dict)
        and canonical_bytes(data['document']) == canonical_bytes(expected)
    )


def verify_or_publish(
    transport: KV2HTTPTransport,
    reference: InventoryStoreReference,
    inventory: dict[str, Any],
    *,
    token: str,
    publish: bool,
) -> None:
    expected = stored_document(reference, inventory)
    if digest(expected) != reference.fingerprint:
        raise SecretProviderError('Inventory store reference does not match the exact document.')
    status, body = transport._request(reference.path, token=token)
    if status == 404 and publish:
        # CAS zero only admits a never-created path, including after a soft
        # deletion. A collision or concurrent write is never overwritten.
        status, written = transport._request(
            reference.path, method='POST', token=token, payload={'options': {'cas': 0}, 'data': {'document': expected}}
        )
        native = written.get('data')
        if status != 200 or not isinstance(native, dict) or type(native.get('version')) is not int or native['version'] != 1:
            raise SecretProviderError('Immutable inventory publication was not confirmed; review the exact path.')
        status, body = transport._request(reference.path, token=token)
    if status != 200 or not _exact_readback(body, expected):
        raise SecretProviderError('Exact inventory version readback is unavailable or mismatched.')

"""Local migration orchestration; no provider writes from web or worker."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import defer, joinedload

from app.extensions.db import db
from app.infrastructure_automation.kubernetes.inventory_document import build_inventory_document, digest
from app.infrastructure_automation.kubernetes.inventory_kv import (
    InventoryStoreReference,
    stored_document,
    verify_or_publish,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPTransport, SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.kv2_transport import validate_auth_mount
from app.integrations.secrets_management.secrets_pki.providers.openbao.client import OpenBaoClient, _verify_inspection_authority
from app.integrations.secrets_management.secrets_pki.providers.openbao.qualification import _require_current_cluster
from app.integrations.secrets_management.secrets_pki.providers.openbao.service import local_provider_enabled
from app.integrations.secrets_management.secrets_pki.providers.vault.client import VaultClient
from app.models.automation import AutomationInventoryAssignment
from app.models.integration import IntegrationInstance
from app.models.openbao import OpenBaoInstance
from app.models.vault import VaultInstance
from app.platform_operations.notifications.service import stage_operational_activity


@dataclass(frozen=True, slots=True)
class LocalInventoryStoreIntent:
    connection_id: int
    provider_id: int
    cluster_id: str
    mount: str
    pod_cidr: str
    service_cidr: str


def _require_scope(intent: LocalInventoryStoreIntent) -> None:
    if (
        not local_provider_enabled()
        or type(intent.connection_id) is not int
        or intent.connection_id < 1
        or type(intent.provider_id) is not int
        or intent.provider_id < 1
        or os.getenv('KAORI_LOCAL_INVENTORY_PROVIDER_ID') != str(intent.provider_id)
        or os.getenv('KAORI_LOCAL_INVENTORY_KV_MOUNT') != intent.mount
        or validate_auth_mount(intent.mount) != intent.mount
        or str(UUID(intent.cluster_id)) != intent.cluster_id
    ):
        raise SecretProviderError('Explicit independently approved local inventory store scope is required.')


def _source(intent: LocalInventoryStoreIntent) -> tuple[IntegrationInstance, dict[str, Any]]:
    connection = db.session.get(IntegrationInstance, intent.connection_id, populate_existing=True)
    if connection is None:
        raise SecretProviderError('Ansible connection is unavailable.')
    assignments = (
        AutomationInventoryAssignment.query.options(joinedload(AutomationInventoryAssignment.host))
        .filter_by(integration_instance_id=connection.id, enabled=True)
        .populate_existing()
        .limit(257)
        .all()
    )
    return connection, build_inventory_document(
        connection, assignments, pod_cidr=intent.pod_cidr, service_cidr=intent.service_cidr
    )


def _provider(intent: LocalInventoryStoreIntent) -> tuple[str, KV2HTTPTransport]:
    identity = db.session.get(IntegrationInstance, intent.provider_id, populate_existing=True)
    if (
        identity is None or identity.integration_type != 'secrets_pki' or not identity.enabled
        or identity.lifecycle_status != 'active'
    ):
        raise SecretProviderError('The exact registered provider is not active.')
    if identity.provider_key == 'openbao' and identity.adapter_key == 'openbao_http_v1':
        row = OpenBaoInstance.query.options(defer(OpenBaoInstance.secret_id)).filter_by(
            integration_instance_id=identity.id
        ).populate_existing().one_or_none()
        if row is None or row.cluster_id != intent.cluster_id:
            raise SecretProviderError('OpenBao cluster identity does not match.')
        if row.ownership == 'internal' and (
            os.getenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER') != 'openbao'
            or os.getenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT') != row.endpoint
            or row.endpoint != 'https://secret-store:8200'
        ):
            raise SecretProviderError('Internal OpenBao deployment ownership changed.')
        provider, endpoint, namespace = OpenBaoClient, row.endpoint, ''
    elif identity.provider_key == 'vault' and identity.adapter_key == 'vault_http_v1':
        vault = VaultInstance.query.options(defer(VaultInstance.secret_id)).filter_by(
            integration_instance_id=identity.id
        ).populate_existing().one_or_none()
        if vault is None or not vault.verify_ssl or intent.mount not in (vault.kv2_mounts or ()) or vault.namespace:
            raise SecretProviderError('An approved root-namespace Vault KV v2 mount is required.')
        provider, endpoint, namespace = VaultClient, vault.endpoint, ''
    else:
        raise SecretProviderError('No supported exact provider; fallback is forbidden.')
    if not os.getenv(provider.ca_bundle_env, '').strip():
        raise SecretProviderError('Explicit provider-specific CA trust is required.')
    transport = KV2HTTPTransport(
        endpoint=endpoint,
        provider_label=provider.provider_label,
        allowed_origins_env=provider.allowed_origins_env,
        ca_bundle_env=provider.ca_bundle_env,
        namespace=namespace,
    )
    if transport.endpoint != endpoint:
        raise SecretProviderError('Provider origin is not canonical.')
    return identity.provider_key, transport


def _cluster(transport: KV2HTTPTransport, provider_key: str, cluster_id: str) -> None:
    if provider_key == 'openbao':
        _require_current_cluster(transport, cluster_id=cluster_id)
        return
    status, data = transport._request('/v1/sys/health')
    if (
        status != 200 or data.get('initialized') is not True or data.get('sealed') is not False
        or data.get('standby') is not False or data.get('performance_standby', False) is not False
        or data.get('cluster_id') != cluster_id
    ):
        raise SecretProviderError('Vault active cluster identity is unqualified.')


def _reference(intent: LocalInventoryStoreIntent, provider_key: str, inventory: dict[str, Any]) -> InventoryStoreReference:
    candidate = InventoryStoreReference(
        intent.provider_id, provider_key, intent.cluster_id, intent.mount, intent.connection_id, ''
    )
    return InventoryStoreReference(
        candidate.provider_id, candidate.provider_key, candidate.cluster_id, candidate.mount,
        candidate.connection_id, digest(stored_document(candidate, inventory))
    )


def _commit_receipt(
    intent: LocalInventoryStoreIntent, reference: InventoryStoreReference, endpoint: str, *, publish: bool
) -> dict[str, Any]:
    _require_scope(intent)
    connection, current = _source(intent)
    provider_key, transport = _provider(intent)
    if _reference(intent, provider_key, current) != reference or transport.endpoint != endpoint:
        raise SecretProviderError('Source or provider changed during readback; no receipt was committed.')
    receipt = {
        'provider_id': reference.provider_id,
        'provider_key': reference.provider_key,
        'cluster_id': reference.cluster_id,
        'mount': reference.mount,
        'fingerprint': reference.fingerprint,
        'host_registry_fingerprint': current['host_registry_fingerprint'],
        'version': 1,
        'observed_at': datetime.now(UTC).isoformat(),
        'execution_authorized': False,
    }
    # This is historical readback evidence, not a lease or currentness grant.
    connection.metadata_json = {**(connection.metadata_json or {}), 'local_inventory_store_receipt': receipt}
    stage_operational_activity(
        user_id=None,
        event_type='automation_local_inventory_store_observed',
        status='success',
        title='Local inventory store observed',
        message='Exact immutable KV v2 configuration and inventory readback observed.',
        metadata={'integration_instance_id': connection.id, 'provider_id': reference.provider_id,
                  'fingerprint': reference.fingerprint, 'version': 1, 'publish_requested': publish},
        delivery_policy='audit_only',
    )
    db.session.commit()
    return receipt


def observe_inventory_store(
    intent: LocalInventoryStoreIntent, *, token: str, publish: bool = False
) -> dict[str, Any]:
    _require_scope(intent)
    if not isinstance(token, str) or not 1 <= len(token) <= 4096 or not token.isascii() or any(
        not 33 <= ord(char) <= 126 for char in token
    ):
        raise SecretProviderError('A transient scoped operator token is required.')
    try:
        _connection, inventory = _source(intent)
        provider_key, transport = _provider(intent)
        reference = _reference(intent, provider_key, inventory)
        db.session.rollback()
        _cluster(transport, provider_key, intent.cluster_id)
        _verify_inspection_authority(transport, token, max_ttl=3600)
        verify_or_publish(transport, reference, inventory, token=token, publish=publish)
        _cluster(transport, provider_key, intent.cluster_id)
        _verify_inspection_authority(transport, token, max_ttl=3600)
        return _commit_receipt(intent, reference, transport.endpoint, publish=publish)
    except Exception:
        db.session.rollback()
        raise

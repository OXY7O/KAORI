"""Exact deployment-owned local OpenBao metadata collection scope."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.kv2_transport import validate_auth_mount
from app.integrations.secrets_management.secrets_pki.providers.openbao.service import local_provider_enabled
from app.models.integration import IntegrationInstance
from app.models.openbao import OpenBaoInstance


@dataclass(frozen=True, slots=True, repr=False)
class LocalOpenBaoInventoryScope:
    instance_id: int
    mount: str
    endpoint: str
    cluster_id: str
    ownership: str


def _require_selected(instance_id: int, mount: str) -> None:
    if (
        not local_provider_enabled()
        or type(instance_id) is not int
        or instance_id < 1
        or os.getenv('KAORI_LOCAL_OPENBAO_INVENTORY_PROVIDER_ID') != str(instance_id)
        or os.getenv('KAORI_LOCAL_OPENBAO_INVENTORY_MOUNT') != mount
        or validate_auth_mount(mount) != mount
    ):
        raise ValueError('Explicit independently approved local inventory scope is required.')


def _source_scope(identity: IntegrationInstance | None, instance_id: int, mount: str, *, lock: bool) -> LocalOpenBaoInventoryScope:
    _require_selected(instance_id, mount)
    if (
        identity is None or identity.id != instance_id or identity.integration_type != 'secrets_pki'
        or identity.provider_key != 'openbao' or identity.adapter_key != 'openbao_http_v1'
        or identity.enabled is not True or identity.lifecycle_status != 'active'
    ):
        raise ValueError('Exact active OpenBao connection required.')
    query = select(OpenBaoInstance).options(load_only(
        OpenBaoInstance.id, OpenBaoInstance.integration_instance_id, OpenBaoInstance.endpoint,
        OpenBaoInstance.cluster_id, OpenBaoInstance.ownership,
    )).where(OpenBaoInstance.integration_instance_id == instance_id).execution_options(populate_existing=True)
    if lock:
        query = query.with_for_update(of=OpenBaoInstance)
    row = db.session.execute(query).scalar_one_or_none()
    if row is None or row.ownership not in ('internal', 'external'):
        raise ValueError('OpenBao connection record unavailable.')
    if row.ownership == 'internal':
        if (
            row.endpoint != 'https://secret-store:8200'
            or os.getenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER') != 'openbao'
            or os.getenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT') != row.endpoint
        ):
            raise ValueError('Internal deployment configuration changed.')
    elif row.endpoint == 'https://secret-store:8200':
        raise ValueError('Invalid external ownership.')
    return LocalOpenBaoInventoryScope(instance_id, mount, row.endpoint, row.cluster_id, row.ownership)


def resolve_local_inventory_scope(instance_id: int, mount: str) -> LocalOpenBaoInventoryScope:
    identity = db.session.get(IntegrationInstance, instance_id, populate_existing=True)
    return _source_scope(identity, instance_id, mount, lock=False)


def require_local_inventory_source(
    scope: LocalOpenBaoInventoryScope, *, identity: IntegrationInstance | None, lock: bool
) -> None:
    if _source_scope(identity, scope.instance_id, scope.mount, lock=lock) != scope:
        raise ValueError('OpenBao deployment or local mount scope changed.')


def current_local_inventory_source(
    identity: IntegrationInstance | None, *, namespace: str, mount: str, lock: bool
) -> LocalOpenBaoInventoryScope | None:
    """Requalify the independently configured local scope without provider I/O or credentials."""
    # Runtime deliberately stays degraded until independent credential authority is admitted.
    if (
        identity is None
        or namespace != ''
        or identity.health_status != 'connected'
        or identity.readiness_status not in ('degraded', 'ready')
    ):
        return None
    try:
        return _source_scope(identity, identity.id, mount, lock=lock)
    except ValueError:
        return None


def local_inventory_deployment_ref(
    identity: IntegrationInstance | None, *, namespace: str, mount: str, environment: str | None, lock: bool
) -> str | None:
    """Stable metadata-only fingerprint; not an issuer or credential authority proof."""
    if (
        identity is None
        or environment not in (
            'development', 'testing', 'staging', 'laboratory', 'sandbox', 'proof_of_concept', 'non_production'
        )
        or os.getenv('KAORI_LOCAL_OPENBAO_AUTOMATION_ENVIRONMENT') != environment
        or identity.environment not in (None, environment)
    ):
        return None
    scope = current_local_inventory_source(identity, namespace=namespace, mount=mount, lock=lock)
    if scope is None:
        return None
    payload = {
        'schema': 'kaori.openbao.local_inventory_source.v1',
        'instance_id': scope.instance_id,
        'endpoint': scope.endpoint,
        'cluster_id': scope.cluster_id,
        'ownership': scope.ownership,
        'mount': scope.mount,
        'environment': environment,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

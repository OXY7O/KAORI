"""Exact deployment-owned local OpenBao metadata collection scope."""

from __future__ import annotations

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

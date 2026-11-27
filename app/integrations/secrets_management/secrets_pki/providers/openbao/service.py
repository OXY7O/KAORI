"""Local OpenBao registration and connection evidence; no credential consumption."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from flask import current_app, has_app_context
from sqlalchemy.exc import SQLAlchemyError

from app.common.pagination import paginate_query
from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.kv2_transport import (
    validate_auth_mount,
    validate_secret_endpoint,
)
from app.integrations.secrets_management.secrets_pki.providers.openbao.client import (
    OpenBaoClient,
    _verify_inspection_authority,
)
from app.integrations.secrets_management.secrets_pki.providers.openbao.qualification import _require_current_cluster
from app.models.integration import IntegrationInstance
from app.models.openbao import OpenBaoInstance
from app.platform_operations.notifications.service import stage_operational_activity

_INTERNAL = 'https://secret-store:8200'


def local_provider_enabled() -> bool:
    return (
        has_app_context()
        and os.getenv('APP_ENV') == 'development'
        and current_app.config.get('APP_ENV') == 'development'
    )


@dataclass(frozen=True, slots=True, repr=False)
class OpenBaoConnectionInput:
    name: str
    ownership: str
    endpoint: str
    cluster_id: str
    auth_mount: str
    role_id: str
    secret_id: str


def _require_connection(values: OpenBaoConnectionInput) -> None:
    if not local_provider_enabled() or not os.getenv(OpenBaoClient.ca_bundle_env, '').strip():
        raise SecretProviderError('OpenBao local development and explicit CA trust are required.')
    if values.ownership not in ('internal', 'external'):
        raise SecretProviderError('Explicit ownership is required.')
    if values.ownership == 'internal':
        if (
            os.getenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER') != 'openbao'
            or os.getenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT') != _INTERNAL
            or values.endpoint != _INTERNAL
        ):
            raise SecretProviderError('Internal OpenBao must match the deployment-owned configuration.')
    elif values.endpoint == _INTERNAL:
        raise SecretProviderError('The bundled endpoint cannot be registered as external.')
    if (
        validate_secret_endpoint(
            values.endpoint, allowed_origins_env=OpenBaoClient.allowed_origins_env, provider_label='OpenBao'
        ) != values.endpoint
        or str(UUID(values.cluster_id)) != values.cluster_id
        or validate_auth_mount(values.auth_mount) != values.auth_mount
        or not 2 <= len(values.name) <= 160
        or not 1 <= len(values.role_id) <= 255
        or not 1 <= len(values.secret_id) <= 4096
    ):
        raise SecretProviderError('Canonical endpoint, cluster UUID and AppRole settings are required.')


def verify_connection(values: OpenBaoConnectionInput) -> None:
    """Fresh identity and AppRole test; token is bounded and never returned."""
    _require_connection(values)
    client = OpenBaoClient(
        endpoint=values.endpoint,
        auth_mount=values.auth_mount,
        role_id=values.role_id,
        secret_id=values.secret_id,
    )
    _require_current_cluster(client, cluster_id=values.cluster_id)
    token = client.login()
    try:
        _verify_inspection_authority(client, token, max_ttl=3600)
        _require_current_cluster(client, cluster_id=values.cluster_id)
    finally:
        del token


def register_connection(values: OpenBaoConnectionInput, *, actor_id: int | None) -> OpenBaoInstance:
    """Register exact connection only after fresh native observation; never mark credential-ready."""
    verify_connection(values)
    try:
        identity = IntegrationInstance()
        identity.integration_type = 'secrets_pki'
        identity.provider_key = 'openbao'
        identity.adapter_key = 'openbao_http_v1'
        identity.name = values.name
        identity.enabled = True
        identity.lifecycle_status = 'active'
        identity.readiness_status = 'validation_required'
        identity.health_status = 'connected'
        identity.last_checked_at = datetime.now(UTC)
        identity.metadata_json = {'provider_label': 'OpenBao', 'ownership': values.ownership, 'auth_type': 'approle'}
        row = OpenBaoInstance()
        row.integration_instance = identity
        row.ownership = values.ownership
        row.internal_slot = 'bundled' if values.ownership == 'internal' else None
        row.endpoint = values.endpoint
        row.cluster_id = values.cluster_id
        row.auth_mount = values.auth_mount
        row.role_id = values.role_id
        row.secret_id = values.secret_id
        row.detected_version = '2.7.3'
        db.session.add(row)
        db.session.flush()
        stage_operational_activity(
            user_id=actor_id,
            event_type='openbao_connection_registered',
            status='success',
            title='OpenBao connection registered',
            message='Local connection verified; independent credential authority remains pending.',
            metadata={'integration_instance_id': identity.id, 'provider': 'openbao', 'ownership': values.ownership},
            delivery_policy='audit_only',
        )
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        raise


def connection_values(row: OpenBaoInstance) -> OpenBaoConnectionInput:
    return OpenBaoConnectionInput(
        row.name, row.ownership, row.endpoint, row.cluster_id, row.auth_mount, row.role_id, row.secret_id
    )


def get_connection(instance_id: int) -> OpenBaoInstance | None:
    return OpenBaoInstance.query.join(OpenBaoInstance.integration_instance).filter(
        OpenBaoInstance.id == instance_id,
        IntegrationInstance.integration_type == 'secrets_pki',
        IntegrationInstance.provider_key == 'openbao',
    ).first()


def list_connections(*, page: int, per_page: int):
    query = OpenBaoInstance.query.join(OpenBaoInstance.integration_instance).filter(
        IntegrationInstance.integration_type == 'secrets_pki', IntegrationInstance.provider_key == 'openbao'
    ).order_by(OpenBaoInstance.id.asc())
    return paginate_query(query, page=page, per_page=per_page)

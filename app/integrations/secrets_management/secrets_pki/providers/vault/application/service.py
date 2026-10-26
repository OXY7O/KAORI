from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.vault.application.forms import VaultConnectionInput
from app.integrations.secrets_management.secrets_pki.providers.vault.client import VaultClient
from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import parse_approved_kv2_mounts
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    parse_approved_pki_mounts,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.transport import (
    validate_auth_mount,
    validate_vault_endpoint,
)
from app.models.integration import IntegrationInstance
from app.models.vault import VaultInstance


def _client(values: VaultConnectionInput) -> VaultClient:
    return VaultClient(
        endpoint=values.endpoint, namespace=values.namespace, auth_mount=values.auth_mount,
        role_id=values.role_id, secret_id=values.secret_id, timeout=values.timeout,
    )


def test_connection(values: VaultConnectionInput) -> dict:
    return _client(values).test_connection()


def save_connection(values: VaultConnectionInput, *, existing: VaultInstance | None = None) -> VaultInstance:
    endpoint = validate_vault_endpoint(values.endpoint)
    mount = validate_auth_mount(values.auth_mount)
    approved_mounts = list(parse_approved_kv2_mounts(','.join(values.kv2_mounts)))
    approved_pki_mounts = list(parse_approved_pki_mounts(','.join(values.pki_mounts)))
    duplicate = IntegrationInstance.query.filter(
        IntegrationInstance.integration_type == 'secrets_pki',
        IntegrationInstance.name == values.name,
    )
    if existing is not None:
        duplicate = duplicate.filter(IntegrationInstance.id != existing.integration_instance_id)
    if duplicate.first() is not None:
        raise ValueError('A Secrets & PKI connection with this name already exists.')
    if existing is None:
        identity = IntegrationInstance()
        identity.integration_type = 'secrets_pki'
        identity.provider_key = 'vault'
        identity.adapter_key = 'vault_http_v1'
        db.session.add(identity)
        db.session.flush()
        instance = VaultInstance()
        instance.integration_instance_id = identity.id
        db.session.add(instance)
    else:
        instance = existing
        identity = instance.integration_instance
    changed = existing is None or any((
        instance.endpoint != endpoint,
        instance.namespace != values.namespace,
        instance.auth_mount != mount,
        instance.role_id != values.role_id,
        instance.secret_id != values.secret_id,
        instance.timeout != values.timeout,
        list(instance.kv2_mounts or ()) != approved_mounts,
        list(instance.pki_mounts or ()) != approved_pki_mounts,
        bool(instance.pki_stored_certs_enabled) != bool(values.pki_stored_certs_enabled),
    ))
    identity.name = values.name
    identity.description = values.description
    identity.environment = values.environment
    identity.enabled = values.enabled
    identity.metadata_json = {
        'provider_label': 'HashiCorp Vault',
        'protocol': 'vault_http_v1',
        'asset_type': 'vault_instance',
        'asset_key': str(identity.id),
        'auth_type': 'approle',
    }
    instance.endpoint = endpoint
    instance.namespace = values.namespace
    instance.auth_mount = mount
    instance.role_id = values.role_id
    instance.secret_id = values.secret_id
    instance.timeout = values.timeout
    instance.kv2_mounts = approved_mounts
    instance.pki_mounts = approved_pki_mounts
    instance.pki_stored_certs_enabled = bool(values.pki_stored_certs_enabled)
    instance.verify_ssl = True
    if changed:
        identity.readiness_status = 'validation_required'
        identity.health_status = None
        identity.last_error = None
        identity.last_checked_at = None
        instance.detected_version = None
        instance.compatibility_status = None
        instance.compatibility_profile = None
        instance.capability_profile = None
        instance.capabilities = None
        instance.validation_summary = None
        instance.validation_message = 'Configuration changed; run Full Validation before operational consumption.'
        instance.last_validated_at = None
        instance.last_response_time_ms = None
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return instance

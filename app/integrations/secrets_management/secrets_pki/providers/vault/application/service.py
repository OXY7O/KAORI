from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.common.pagination import paginate_query
from app.integrations.deletion import DeletionBlocked, DeletionGuard, provider_deletion_guard
from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.vault.application.types import VaultConnectionInput
from app.integrations.secrets_management.secrets_pki.providers.vault.client import VaultClient
from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import parse_approved_kv2_mounts
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    parse_approved_pki_mounts,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.transport import (
    validate_auth_mount,
    validate_vault_endpoint,
)
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.secrets_pki import SecretInventoryCollectionState, SecretProviderRepresentation
from app.models.secrets_pki_pki import PKIIssuerCollectionState, PKIIssuerIdentity
from app.models.secrets_pki_stored_certificates import (
    PKIStoredCertificateCollectionState,
    PKIStoredCertificateObservation,
)
from app.platform_operations.jobs.service import acquire_resource_admission_locks
from app.models.runtime import IntegrationRuntimeObservation
from app.models.vault import VaultInstance


def _client(values: VaultConnectionInput) -> VaultClient:
    return VaultClient(
        endpoint=values.endpoint,
        namespace=values.namespace,
        auth_mount=values.auth_mount,
        role_id=values.role_id,
        secret_id=values.secret_id,
        timeout=values.timeout,
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
        # Registry identity has NOT NULL columns. Populate them before flush
        # obtains the generated canonical id; metadata_json follows the id.
        identity = IntegrationInstance()
        identity.integration_type = 'secrets_pki'
        identity.provider_key = 'vault'
        identity.adapter_key = 'vault_http_v1'
        identity.name = values.name
        identity.description = values.description
        identity.environment = values.environment
        identity.enabled = values.enabled
        db.session.add(identity)
        try:
            db.session.flush()
        except SQLAlchemyError:
            # A failed flush leaves the scoped Session in PendingRollback.
            # Recover it before the route writes its Activity Audit feedback.
            db.session.rollback()
            raise
        instance = VaultInstance()
        instance.integration_instance_id = identity.id
        db.session.add(instance)
    else:
        instance = existing
        identity = instance.integration_instance
    changed = existing is None or any(
        (
            instance.endpoint != endpoint,
            instance.namespace != values.namespace,
            instance.auth_mount != mount,
            instance.role_id != values.role_id,
            instance.secret_id != values.secret_id,
            instance.timeout != values.timeout,
            list(instance.kv2_mounts or ()) != approved_mounts,
            list(instance.pki_mounts or ()) != approved_pki_mounts,
            bool(instance.pki_stored_certs_enabled) != bool(values.pki_stored_certs_enabled),
        )
    )
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


def vault_connection_deletion_guard(instance: VaultInstance) -> DeletionGuard:
    """Fail closed on active work and committed Secrets/PKI dependencies.

    All downstream Secret/PKI evidence is retained by its canonical
    integration identity under RESTRICT foreign keys. A provider registration
    with committed evidence cannot be deleted without a separately approved
    evidence-retention/migration workflow.
    """
    canonical_id = instance.integration_instance_id
    existing = provider_deletion_guard(
        integration_type='secrets_pki',
        integration_instance_id=canonical_id,
    )
    blockers = (
        (IntegrationBinding, 'integration bindings'),
        (SecretProviderRepresentation, 'Secret representations'),
        (SecretInventoryCollectionState, 'KV v2 collection states'),
        (PKIIssuerIdentity, 'PKI issuers'),
        (PKIIssuerCollectionState, 'public PKI collection states'),
        (PKIStoredCertificateObservation, 'stored PKI certificates'),
        (PKIStoredCertificateCollectionState, 'stored PKI collection states'),
    )
    reasons = list(existing.reasons)
    for model, label in blockers:
        count = model.query.filter_by(integration_instance_id=canonical_id).count()
        if count:
            reasons.append(f'{count} {label} still reference this connection.')
    return DeletionGuard(
        blocked=bool(reasons),
        reasons=tuple(reasons),
        active_jobs=existing.active_jobs,
    )


def delete_vault_connection(instance: VaultInstance) -> None:
    """Remove only the unreferenced Vault credential and KAORI registration.

    Runtime observations, historical JobExecution and Activity Audit are
    independent owner records and are not deleted. Vault itself is untouched.
    """
    acquire_resource_admission_locks(f'integration:secrets_pki:{instance.integration_instance_id}')
    guard = vault_connection_deletion_guard(instance)
    if guard.blocked:
        raise DeletionBlocked(guard)
    canonical = instance.integration_instance
    try:
        db.session.delete(instance)
        db.session.flush()
        db.session.delete(canonical)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise


def get_vault_connection_instance(instance_id: int) -> VaultInstance | None:
    """Resolve an existing provider connection; HTTP layers own 404 responses."""
    return VaultInstance.query.filter_by(id=instance_id).first()


def list_vault_connection_registry(
    *,
    search: str,
    environment: str,
    readiness_filter: str,
    page: int,
    per_page: int,
) -> tuple[list[VaultInstance], dict[str, Any], int, int, int]:
    """Return the committed provider registry and posture without web globals."""
    query = VaultInstance.query.join(VaultInstance.integration_instance).order_by(VaultInstance.id.asc())
    registered = query.count()
    filtered = query
    if search:
        filtered = filtered.filter(
            IntegrationInstance.name.icontains(search, autoescape=True)
            | VaultInstance.endpoint.icontains(search, autoescape=True)
        )
    if environment:
        filtered = filtered.filter(IntegrationInstance.environment == environment)
    if readiness_filter:
        filtered = filtered.filter(IntegrationInstance.readiness_status == readiness_filter)
    instances, pagination = paginate_query(filtered, page=page, per_page=per_page)
    enabled = query.filter(
        IntegrationInstance.enabled.is_(True),
        IntegrationInstance.lifecycle_status == 'active',
    ).count()
    ready = query.filter(
        IntegrationInstance.enabled.is_(True),
        IntegrationInstance.lifecycle_status == 'active',
        IntegrationInstance.readiness_status == 'ready',
    ).count()
    return instances, pagination, registered, enabled, ready


def latest_vault_runtime_observation(instance_id: int) -> IntegrationRuntimeObservation | None:
    """Read the most recent committed runtime evidence for a Vault connection."""
    return (
        IntegrationRuntimeObservation.query.filter_by(
            integration_type='secrets_pki',
            instance_id=str(instance_id),
        )
        .order_by(IntegrationRuntimeObservation.observed_at.desc(), IntegrationRuntimeObservation.id.desc())
        .first()
    )

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.deletion import DeletionBlocked, asset_owner_deletion_guard
from app.integrations.registry.providers.harbor.application.contracts import HarborRegistrationInput
from app.integrations.registry.providers.harbor.client import HarborClient
from app.integrations.registry.providers.harbor.contracts import HarborConnectionResult
from app.models.harbor import HarborInstance
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.platform_operations.jobs.service import acquire_resource_admission_locks


def get_harbor_instance(instance_id: int) -> HarborInstance | None:
    return HarborInstance.query.filter_by(id=instance_id).first()


def test_harbor_connection(values: HarborRegistrationInput) -> HarborConnectionResult:
    client = HarborClient(
        endpoint=values.endpoint,
        auth_type=values.auth_type,
        username=values.username,
        password=values.password,
        timeout=values.timeout,
        verify_ssl=values.verify_ssl,
    )
    # Test Connection proves endpoint identity/reachability only.
    # Compatibility and required capability evidence remain Full Validation authority.
    return client.test_connection()


def create_harbor_instance(values: HarborRegistrationInput) -> HarborInstance:
    if IntegrationInstance.query.filter_by(integration_type='registry', name=values.name).first() is not None:
        raise ValueError('A Registry connection with this name already exists.')

    canonical = IntegrationInstance()
    canonical.integration_type = 'registry'
    canonical.provider_key = 'harbor'
    canonical.adapter_key = 'harbor_api_v2'
    canonical.name = values.name
    canonical.description = values.description
    canonical.environment = values.environment
    canonical.enabled = values.enabled
    canonical.readiness_status = 'validation_required'
    canonical.health_status = None
    db.session.add(canonical)
    db.session.flush()

    instance = HarborInstance()
    instance.integration_instance_id = canonical.id
    instance.endpoint = values.endpoint
    instance.auth_type = values.auth_type
    instance.username = values.username
    instance.password = values.password
    instance.timeout = values.timeout
    instance.verify_ssl = values.verify_ssl
    db.session.add(instance)
    db.session.flush()

    canonical.metadata_json = {
        'provider_label': 'Harbor',
        'protocol': 'harbor_api_v2',
        'auth_type': values.auth_type,
        'asset_type': 'registry_instance',
        'asset_key': str(canonical.id),
    }
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return instance


def update_harbor_instance(instance: HarborInstance, values: HarborRegistrationInput) -> HarborInstance:
    duplicate = IntegrationInstance.query.filter(
        IntegrationInstance.integration_type == 'registry',
        IntegrationInstance.name == values.name,
        IntegrationInstance.id != instance.integration_instance_id,
    ).first()
    if duplicate is not None:
        raise ValueError('A Registry connection with this name already exists.')

    connection_changed = any(
        (
            instance.endpoint != values.endpoint,
            instance.auth_type != values.auth_type,
            instance.username != values.username,
            (str(instance.password) if instance.password is not None else None) != values.password,
            instance.timeout != values.timeout,
            instance.verify_ssl != values.verify_ssl,
        )
    )

    canonical = instance.integration_instance
    canonical.name = values.name
    canonical.description = values.description
    canonical.environment = values.environment
    canonical.enabled = values.enabled

    instance.endpoint = values.endpoint
    instance.auth_type = values.auth_type
    instance.username = values.username
    instance.password = values.password
    instance.timeout = values.timeout
    instance.verify_ssl = values.verify_ssl

    if connection_changed:
        canonical.readiness_status = 'validation_required'
        canonical.health_status = None
        canonical.last_error = None
        canonical.last_checked_at = None
        instance.detected_version = None
        instance.compatibility_status = None
        instance.compatibility_profile = None
        instance.capability_profile = None
        instance.capabilities = None
        instance.validation_summary = None
        instance.validation_message = (
            'Harbor connection settings changed. Run Full Validation before KAORI treats this provider as ready.'
        )
        instance.last_validated_at = None
        instance.last_response_time_ms = None

    canonical.metadata_json = {
        **(canonical.metadata_json or {}),
        'provider_label': 'Harbor',
        'protocol': 'harbor_api_v2',
        'auth_type': values.auth_type,
        'asset_type': 'registry_instance',
        'asset_key': str(canonical.id),
    }
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return instance


def delete_harbor_instance(instance: HarborInstance) -> dict[str, int]:
    """Delete KAORI-owned Harbor registration state without mutating Harbor.

    The canonical Registry integration identity is also the provider-neutral
    ``registry_instance`` consumer asset. Deleting it removes committed
    provider-derived Registry state through existing foreign-key ownership and
    removes bindings that target this Registry instance. Reusable Metrics Source
    and Alertmanager connections remain registered. Runtime observations,
    JobExecution history, and Activity Audit evidence remain retained by their
    independent history contracts.
    """
    integration_instance_id = int(instance.integration_instance_id)
    asset_key = str(integration_instance_id)
    acquire_resource_admission_locks(
        f'integration:registry:{integration_instance_id}',
        f'registry_instance:{asset_key}',
    )
    guard = asset_owner_deletion_guard(
        integration_type='registry',
        integration_instance_id=integration_instance_id,
        asset_type='registry_instance',
        asset_key=asset_key,
    )
    if guard.blocked:
        raise DeletionBlocked(guard)

    canonical = instance.integration_instance
    deleted_bindings = IntegrationBinding.query.filter(
        IntegrationBinding.asset_type == 'registry_instance',
        IntegrationBinding.asset_key == asset_key,
    ).delete(synchronize_session=False)

    db.session.delete(instance)
    db.session.flush()
    if canonical is not None:
        db.session.delete(canonical)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return {
        'asset_bindings': int(deleted_bindings or 0),
        'canonical_instance_deleted': int(canonical is not None),
    }

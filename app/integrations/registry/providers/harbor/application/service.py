from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.registry.providers.harbor.application.contracts import HarborRegistrationInput
from app.integrations.registry.providers.harbor.client import HarborClient
from app.models.harbor import HarborInstance
from app.models.integration import IntegrationInstance


def get_harbor_instance(instance_id: int) -> HarborInstance | None:
    return HarborInstance.query.filter_by(id=instance_id).first()


def test_harbor_connection(values: HarborRegistrationInput) -> dict[str, object]:
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

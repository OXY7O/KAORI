from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.deletion import DeletionBlocked, asset_owner_deletion_guard
from app.integrations.storage.object_storage.providers.minio.application.contracts import MinioRegistrationInput
from app.integrations.storage.object_storage.providers.minio.capabilities import OBJECT_STORAGE_SYSTEM_SCOPE
from app.integrations.storage.object_storage.providers.minio.client import MinioConnectionResult, test_connection_values
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.metrics_source import MetricsSource
from app.models.minio import MinioInstance
from app.models.object_storage import ObjectStorageSystem
from app.platform_operations.jobs.service import acquire_resource_admission_locks


def get_minio_instance(instance_id: int) -> MinioInstance | None:
    return MinioInstance.query.filter_by(id=instance_id).first()


def test_minio_connection(values: MinioRegistrationInput) -> MinioConnectionResult:
    result = test_connection_values(
        endpoint=values.endpoint,
        access_key=values.access_key,
        secret_key=values.secret_key,
        region=values.region,
        addressing_style=values.addressing_style,
        timeout=values.timeout,
        verify_ssl=values.verify_ssl,
    )
    # Registration Test Connection proves endpoint/authentication/S3 access only.
    # Product identity and release compatibility remain authoritative Core Validation evidence.
    return result


def create_minio_instance(values: MinioRegistrationInput) -> MinioInstance:
    name = values.name
    if IntegrationInstance.query.filter_by(integration_type='object_storage', name=name).first() is not None:
        raise ValueError('A MinIO connection with this name already exists.')
    if ObjectStorageSystem.query.filter_by(name=name).first() is not None:
        raise ValueError('An object-storage asset with this name already exists.')

    canonical = IntegrationInstance()
    canonical.integration_type = 'object_storage'
    canonical.provider_key = 'minio'
    canonical.adapter_key = 's3'
    canonical.name = name
    canonical.description = values.description
    canonical.environment = values.environment
    canonical.enabled = values.enabled
    canonical.readiness_status = 'validation_required'
    canonical.health_status = None
    db.session.add(canonical)
    db.session.flush()

    asset = ObjectStorageSystem()
    asset.name = name
    asset.environment = values.environment
    asset.description = values.description
    asset.status = 'unknown'
    db.session.add(asset)
    db.session.flush()

    instance = MinioInstance()
    instance.integration_instance_id = canonical.id
    instance.object_storage_system_id = asset.id
    instance.endpoint = values.endpoint
    instance.access_key = values.access_key
    instance.secret_key = values.secret_key
    instance.region = values.region
    instance.addressing_style = values.addressing_style
    instance.timeout = values.timeout
    instance.verify_ssl = values.verify_ssl
    instance.declared_release = values.declared_release
    db.session.add(instance)
    db.session.flush()

    canonical.metadata_json = {
        'asset_type': OBJECT_STORAGE_SYSTEM_SCOPE,
        'asset_key': asset.id,
        'endpoint_product': 'minio',
        'provider_label': 'MinIO',
        'declared_release': instance.declared_release,
    }
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return instance


def update_minio_instance(instance: MinioInstance, values: MinioRegistrationInput) -> MinioInstance:
    duplicate_canonical = IntegrationInstance.query.filter(
        IntegrationInstance.integration_type == 'object_storage',
        IntegrationInstance.name == values.name,
        IntegrationInstance.id != instance.integration_instance_id,
    ).first()
    if duplicate_canonical is not None:
        raise ValueError('A MinIO connection with this name already exists.')
    duplicate_asset = ObjectStorageSystem.query.filter(
        ObjectStorageSystem.name == values.name,
        ObjectStorageSystem.id != instance.object_storage_system_id,
    ).first()
    if duplicate_asset is not None:
        raise ValueError('An object-storage asset with this name already exists.')

    connection_changed = any(
        (
            instance.endpoint != values.endpoint,
            instance.access_key != values.access_key,
            str(instance.secret_key) != values.secret_key,
            instance.region != values.region,
            instance.addressing_style != values.addressing_style,
            instance.timeout != values.timeout,
            instance.verify_ssl != values.verify_ssl,
            instance.declared_release != values.declared_release,
        )
    )

    canonical = instance.integration_instance
    asset = instance.object_storage_system
    canonical.name = values.name
    canonical.description = values.description
    canonical.environment = values.environment
    canonical.enabled = values.enabled
    asset.name = values.name
    asset.description = values.description
    asset.environment = values.environment

    instance.endpoint = values.endpoint
    instance.access_key = values.access_key
    instance.secret_key = values.secret_key
    instance.region = values.region
    instance.addressing_style = values.addressing_style
    instance.timeout = values.timeout
    instance.verify_ssl = values.verify_ssl
    instance.declared_release = values.declared_release

    if connection_changed:
        canonical.readiness_status = 'validation_required'
        canonical.health_status = None
        canonical.last_error = None
        canonical.last_checked_at = None
        instance.detected_product = None
        instance.observed_server_header = None
        instance.deployment_id = None
        instance.compatibility_status = None
        instance.compatibility_profile = None
        instance.capability_profile = None
        instance.capabilities = None
        instance.validation_summary = None
        instance.validation_message = (
            'MinIO connection settings changed. Run Core Validation before KAORI treats this provider as ready.'
        )
        instance.last_validated_at = None
        asset.status = 'unknown'
        asset.last_check = None

    canonical.metadata_json = {
        **(canonical.metadata_json or {}),
        'asset_type': OBJECT_STORAGE_SYSTEM_SCOPE,
        'asset_key': asset.id,
        'endpoint_product': 'minio',
        'provider_label': 'MinIO',
        'declared_release': instance.declared_release,
    }
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return instance


def delete_minio_instance(instance: MinioInstance) -> dict[str, int]:
    """Delete a MinIO asset-owner connection and only its asset-scoped bindings.

    Bound observability source connections remain reusable. Runtime observation
    and Activity Audit history are intentionally retained by their canonical history
    models. The object-storage asset and every binding that targets it are removed
    together with the MinIO connection identity.
    """
    asset_key = str(instance.object_storage_system_id)
    acquire_resource_admission_locks(
        f'integration:object_storage:{instance.integration_instance_id}',
        f'{OBJECT_STORAGE_SYSTEM_SCOPE}:{asset_key}',
    )
    guard = asset_owner_deletion_guard(
        integration_type='object_storage',
        integration_instance_id=instance.integration_instance_id,
        asset_type=OBJECT_STORAGE_SYSTEM_SCOPE,
        asset_key=asset_key,
    )
    if guard.blocked:
        raise DeletionBlocked(guard)

    canonical = instance.integration_instance
    asset = instance.object_storage_system
    deleted_bindings = IntegrationBinding.query.filter(
        IntegrationBinding.asset_type == OBJECT_STORAGE_SYSTEM_SCOPE,
        IntegrationBinding.asset_key == asset_key,
    ).delete(synchronize_session=False)

    # Deleting the asset removes future evidence, not the historical alert condition.
    # Hold open KAORI cases as Unknown so deletion can never be mistaken for recovery.
    from app.intelligence.alert_intelligence.lifecycle import mark_asset_alert_cases_source_unknown

    alert_cases_marked_unknown = mark_asset_alert_cases_source_unknown(
        domain='object_storage',
        asset_key=asset_key,
        reason='source_deleted',
        source_kind='object_storage',
    )

    # Provider implementation records point inward to the provider-neutral asset;
    # the asset core does not expose a MinIO-specific reverse relationship. Remove
    # the implementation record explicitly, then the asset and canonical identity.
    db.session.delete(instance)
    db.session.flush()
    db.session.delete(asset)
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
        'object_storage_asset_deleted': 1,
        'canonical_instance_deleted': int(canonical is not None),
        'alert_cases_marked_unknown': int(alert_cases_marked_unknown),
    }


def current_metrics_binding(instance: MinioInstance) -> IntegrationBinding | None:
    return (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationInstance.integration_type == 'metrics_source',
            IntegrationInstance.enabled.is_(True),
            IntegrationBinding.asset_type == OBJECT_STORAGE_SYSTEM_SCOPE,
            IntegrationBinding.asset_key == instance.object_storage_system_id,
            IntegrationBinding.binding_role == 'primary',
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc())
        .first()
    )


def metrics_source_for_binding(binding: IntegrationBinding | None) -> MetricsSource | None:
    if binding is None:
        return None
    canonical = db.session.get(IntegrationInstance, binding.integration_instance_id)
    if canonical is None or canonical.integration_type != 'metrics_source':
        return None
    return MetricsSource.query.filter_by(integration_instance_id=canonical.id).first()


def current_alert_binding(instance: MinioInstance) -> IntegrationBinding | None:
    return (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationInstance.integration_type == 'alert_source',
            IntegrationInstance.enabled.is_(True),
            IntegrationBinding.asset_type == OBJECT_STORAGE_SYSTEM_SCOPE,
            IntegrationBinding.asset_key == instance.object_storage_system_id,
            IntegrationBinding.binding_role == 'primary',
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc())
        .first()
    )


def alert_source_for_binding(binding: IntegrationBinding | None) -> AlertmanagerInstance | None:
    if binding is None:
        return None
    canonical = db.session.get(IntegrationInstance, binding.integration_instance_id)
    if canonical is None or canonical.integration_type != 'alert_source':
        return None
    return AlertmanagerInstance.query.filter_by(integration_instance_id=canonical.id).first()


def mark_registration_test_observation(instance: MinioInstance, result: MinioConnectionResult) -> None:
    now = datetime.now(UTC)
    instance.detected_product = result.product
    instance.observed_server_header = result.server_header
    instance.deployment_id = result.deployment_id
    instance.last_response_time_ms = result.latency_ms
    instance.last_checked_at = now
    instance.last_status = 'connected'
    instance.last_error = None
    instance.object_storage_system.status = 'connected'
    instance.object_storage_system.last_check = now
    db.session.commit()

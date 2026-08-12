from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.alertmanager.capabilities import BINDING_CAPABILITY_KEYS as ALERTMANAGER_CAPABILITY_SCOPE
from app.integrations.binding_service import SourceBindingSpec, create_source_binding
from app.integrations.minio.binding import ensure_primary_asset_binding
from app.integrations.minio.capabilities import OBJECT_STORAGE_SYSTEM_SCOPE, PROMETHEUS_CAPABILITY_SCOPE
from app.integrations.minio.client import MinioConnectionResult, test_connection_values
from app.minio.contracts import MinioAlertBindingInput, MinioMetricsBindingInput, MinioRegistrationInput
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.minio import MinioInstance
from app.models.object_storage import ObjectStorageSystem
from app.models.prometheus import PrometheusInstance


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
    if IntegrationInstance.query.filter_by(provider_type='minio', name=name).first() is not None:
        raise ValueError('A MinIO connection with this name already exists.')
    if ObjectStorageSystem.query.filter_by(name=name).first() is not None:
        raise ValueError('An object-storage asset with this name already exists.')

    canonical = IntegrationInstance()
    canonical.provider_type = 'minio'
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
        'declared_release': instance.declared_release,
    }
    ensure_primary_asset_binding(instance, commit=False)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return instance


def prometheus_choices() -> list[tuple[int, str]]:
    rows = (
        PrometheusInstance.query.join(PrometheusInstance.integration_instance)
        .filter(IntegrationInstance.enabled.is_(True), IntegrationInstance.lifecycle_status == 'active')
        .order_by(IntegrationInstance.name.asc())
        .all()
    )
    return [(row.id, row.name) for row in rows]


def bind_prometheus_metrics(instance: MinioInstance, values: MinioMetricsBindingInput) -> IntegrationBinding:
    if current_metrics_binding(instance) is not None:
        raise ValueError('This object-storage asset already has an enabled primary Prometheus binding.')
    result = create_source_binding(
        'prometheus',
        source_id=values.prometheus_instance_id,
        spec=SourceBindingSpec(
            asset_type=OBJECT_STORAGE_SYSTEM_SCOPE,
            asset_key=instance.object_storage_system_id,
            role='primary',
            priority=100,
            selector_label=values.selector_label,
            selector_value=values.selector_value,
            selector_operator=values.selector_operator,
            capability_scope=list(PROMETHEUS_CAPABILITY_SCOPE),
        ),
        asset=instance.object_storage_system,
    )
    return result.binding


def current_metrics_binding(instance: MinioInstance) -> IntegrationBinding | None:
    return (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationInstance.provider_type == 'prometheus',
            IntegrationInstance.enabled.is_(True),
            IntegrationBinding.asset_type == OBJECT_STORAGE_SYSTEM_SCOPE,
            IntegrationBinding.asset_key == instance.object_storage_system_id,
            IntegrationBinding.binding_role == 'primary',
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc())
        .first()
    )


def metrics_source_for_binding(binding: IntegrationBinding | None) -> PrometheusInstance | None:
    if binding is None:
        return None
    canonical = db.session.get(IntegrationInstance, binding.integration_instance_id)
    if canonical is None or canonical.provider_type != 'prometheus':
        return None
    return PrometheusInstance.query.filter_by(integration_instance_id=canonical.id).first()


def remove_metrics_binding(instance: MinioInstance) -> bool:
    binding = current_metrics_binding(instance)
    if binding is None:
        return False
    db.session.delete(binding)
    db.session.commit()
    return True


def alertmanager_choices() -> list[tuple[int, str]]:
    rows = (
        AlertmanagerInstance.query.join(AlertmanagerInstance.integration_instance)
        .filter(IntegrationInstance.enabled.is_(True), IntegrationInstance.lifecycle_status == 'active')
        .order_by(IntegrationInstance.name.asc())
        .all()
    )
    return [(row.id, row.name) for row in rows]


def bind_alertmanager_alerts(instance: MinioInstance, values: MinioAlertBindingInput) -> IntegrationBinding:
    if current_alert_binding(instance) is not None:
        raise ValueError('This object-storage asset already has an enabled primary Alertmanager binding.')
    result = create_source_binding(
        'alertmanager',
        source_id=values.alertmanager_instance_id,
        spec=SourceBindingSpec(
            asset_type=OBJECT_STORAGE_SYSTEM_SCOPE,
            asset_key=instance.object_storage_system_id,
            role='primary',
            priority=100,
            selector_label=values.selector_label,
            selector_value=values.selector_value,
            selector_operator=values.selector_operator,
            capability_scope=list(ALERTMANAGER_CAPABILITY_SCOPE),
        ),
        asset=instance.object_storage_system,
    )
    return result.binding


def current_alert_binding(instance: MinioInstance) -> IntegrationBinding | None:
    return (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationInstance.provider_type == 'alertmanager',
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
    if canonical is None or canonical.provider_type != 'alertmanager':
        return None
    return AlertmanagerInstance.query.filter_by(integration_instance_id=canonical.id).first()


def remove_alert_binding(instance: MinioInstance) -> bool:
    binding = current_alert_binding(instance)
    if binding is None:
        return False
    db.session.delete(binding)
    db.session.commit()
    return True


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

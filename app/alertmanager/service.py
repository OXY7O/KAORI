from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.alertmanager.bindings import create_or_update_binding, delete_binding, resolve_sources
from app.alertmanager.client_factory import build_client
from app.alertmanager.consumer import (
    KUBERNETES_CLUSTER_SCOPE,
    get_scope_status,
    list_alerts_for_scope,
    list_silences_for_scope,
)
from app.alertmanager.forms import (
    AlertmanagerBindingForm,
    AlertmanagerConfigForm,
    AlertmanagerInstanceForm,
    validate_endpoint,
)
from app.alertmanager.repository import (
    get_instance,
    get_instance_by_name,
    get_legacy_config_by_cluster_id,
    list_bindings_for_instance,
    list_instances,
)
from app.alertmanager.validation import validate_source
from app.extensions import db
from app.models.alertmanager import AlertmanagerBinding, AlertmanagerConfig, AlertmanagerInstance
from app.models.cluster import Cluster


def get_cluster_by_id(cluster_id: str) -> Cluster | None:
    return db.session.get(Cluster, cluster_id)


def get_alertmanager_instance(instance_id: int) -> AlertmanagerInstance | None:
    return get_instance(instance_id)


def list_alertmanager_instances() -> list[AlertmanagerInstance]:
    return list_instances()


def save_alertmanager_instance(
    *,
    form: AlertmanagerInstanceForm,
    instance: AlertmanagerInstance | None = None,
    commit: bool = True,
) -> AlertmanagerInstance:
    if not form.name:
        raise ValueError('Instance name is required.')
    validate_endpoint(form.endpoint)

    duplicate = get_instance_by_name(form.name)
    if duplicate is not None and (instance is None or duplicate.id != instance.id):
        raise ValueError('An Alertmanager instance with this name already exists.')

    creating = instance is None
    if instance is None:
        instance = AlertmanagerInstance()
        db.session.add(instance)

    previous_auth_type = instance.auth_type if not creating else 'none'
    instance.name = form.name
    instance.description = form.description
    instance.deployment_type = form.deployment_type
    instance.endpoint = form.endpoint
    instance.auth_type = form.auth_type
    instance.username = form.username if form.auth_type == 'basic' else None
    if form.auth_type == 'basic':
        if form.password is not None:
            instance.password = form.password
        elif previous_auth_type != 'basic':
            instance.password = None
    else:
        instance.password = None
    if form.auth_type == 'bearer':
        if form.bearer_token is not None:
            instance.bearer_token = form.bearer_token
        elif previous_auth_type != 'bearer':
            instance.bearer_token = None
    else:
        instance.bearer_token = None
    instance.timeout = form.timeout
    instance.verify_ssl = form.verify_ssl
    instance.enabled = form.enabled
    instance.updated_at = datetime.now(UTC)
    instance.compatibility_status = 'validation_required'
    instance.readiness_status = 'validation_required'
    instance.compatibility_profile = None
    instance.capabilities = None
    instance.validation_message = 'Configuration changed. Run validation before KAORI uses this integration.'
    instance.last_validated_at = None
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    else:
        db.session.flush()
    return instance


def create_alertmanager_instance(
    *,
    form: AlertmanagerInstanceForm,
    initial_binding: AlertmanagerBindingForm | None = None,
) -> AlertmanagerInstance:
    try:
        instance = save_alertmanager_instance(form=form, commit=False)
        if initial_binding is not None:
            create_or_update_binding(
                instance=instance,
                form=initial_binding,
                commit=False,
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return instance


def remove_alertmanager_instance(instance: AlertmanagerInstance) -> None:
    if instance.bindings:
        raise ValueError('Remove all asset bindings before deleting this Alertmanager instance.')
    db.session.delete(instance)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def validate_alertmanager_instance(instance: AlertmanagerInstance) -> dict[str, Any]:
    return validate_source(instance, source_label=instance.name).to_dict()


def add_alertmanager_binding(
    *,
    instance: AlertmanagerInstance,
    form: AlertmanagerBindingForm,
    commit: bool = True,
) -> AlertmanagerBinding:
    return create_or_update_binding(instance=instance, form=form, commit=commit)


def remove_alertmanager_binding(binding_id: int) -> AlertmanagerBinding | None:
    return delete_binding(binding_id)


def get_alertmanager_binding(binding_id: int) -> AlertmanagerBinding | None:
    from app.alertmanager.repository import get_binding

    return get_binding(binding_id)


def get_alertmanager_bindings(instance_id: int) -> list[AlertmanagerBinding]:
    return list_bindings_for_instance(instance_id)


def materialize_legacy_cluster_config(cluster_id: str) -> AlertmanagerInstance | None:
    sources = resolve_sources(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)
    if sources:
        return sources[0]

    legacy = get_legacy_config_by_cluster_id(cluster_id)
    cluster = get_cluster_by_id(cluster_id)
    if legacy is None or cluster is None or not legacy.endpoint:
        return None

    base_name = f'{cluster.name} Alertmanager'
    name = base_name
    suffix = 2
    while get_instance_by_name(name) is not None:
        name = f'{base_name} {suffix}'
        suffix += 1

    instance = AlertmanagerInstance()
    instance.name = name
    instance.description = f'Migrated from the legacy cluster-scoped Alertmanager configuration for {cluster.name}.'
    instance.deployment_type = 'cluster_managed'
    _copy_legacy_config(legacy, instance)
    db.session.add(instance)
    db.session.flush()

    binding = AlertmanagerBinding()
    binding.alertmanager_instance_id = instance.id
    binding.scope_type = KUBERNETES_CLUSTER_SCOPE
    binding.scope_key = cluster_id
    binding.binding_role = 'primary'
    binding.priority = 100
    binding.enabled = True
    db.session.add(binding)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return instance


def get_alertmanager_config_by_cluster_id(cluster_id: str) -> AlertmanagerConfig | None:
    return get_legacy_config_by_cluster_id(cluster_id)


def get_or_create_alertmanager_config(cluster_id: str) -> AlertmanagerConfig:
    config = get_legacy_config_by_cluster_id(cluster_id)
    if config is not None:
        return config
    config = AlertmanagerConfig()
    config.cluster_id = cluster_id
    config.endpoint = ''
    config.auth_type = 'none'
    config.timeout = 5
    config.verify_ssl = True
    db.session.add(config)
    return config


def save_alertmanager_config(*, cluster_id: str, form: AlertmanagerConfigForm) -> AlertmanagerConfig:
    """Legacy write path retained only for compatibility with external imports."""
    config = get_or_create_alertmanager_config(cluster_id)
    config.endpoint = form.endpoint
    config.auth_type = form.auth_type
    config.username = form.username if form.auth_type == 'basic' else None
    config.password = form.password if form.auth_type == 'basic' else None
    config.bearer_token = form.bearer_token if form.auth_type == 'bearer' else None
    config.timeout = form.timeout
    config.verify_ssl = form.verify_ssl
    config.updated_at = datetime.now(UTC)
    config.compatibility_status = 'validation_required'
    config.readiness_status = 'validation_required'
    config.compatibility_profile = None
    config.validation_message = 'Configuration changed. Run validation before KAORI uses this integration.'
    config.last_validated_at = None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return config


def build_alertmanager_client(config: AlertmanagerInstance | AlertmanagerConfig):
    return build_client(config)


def test_alertmanager_connection(*, cluster_id: str) -> dict[str, Any]:
    sources = resolve_sources(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)
    if sources:
        return validate_alertmanager_instance(sources[0])
    legacy = get_legacy_config_by_cluster_id(cluster_id)
    if legacy is None:
        return {
            'connected': False,
            'label': 'Alertmanager Not Configured',
            'error': 'No Alertmanager source is bound to this Kubernetes cluster.',
            'reason': 'Integration is not configured',
            'failure_code': 'not_configured',
        }
    return validate_source(legacy, source_label=f'cluster {cluster_id}').to_dict()


def get_alertmanager_status(*, cluster_id: str) -> dict[str, Any]:
    return get_scope_status(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)


def get_alertmanager_alerts(*, cluster_id: str) -> dict[str, Any]:
    return list_alerts_for_scope(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)


def get_alertmanager_silences(*, cluster_id: str) -> dict[str, Any]:
    return list_silences_for_scope(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)


def mark_alertmanager_status(
    *,
    config: AlertmanagerConfig,
    status: str,
    error: str | None,
    response_time_ms: int | None,
) -> None:
    from app.alertmanager.status import mark_status

    mark_status(config, status=status, error=error, response_time_ms=response_time_ms)


def build_alertmanager_config_context(*, cluster_id: str) -> dict[str, Any]:
    cluster = get_cluster_by_id(cluster_id)
    instance = materialize_legacy_cluster_config(cluster_id)
    return {
        'cluster': cluster,
        'config': instance or get_legacy_config_by_cluster_id(cluster_id),
        'instance': instance,
        'status': get_alertmanager_status(cluster_id=cluster_id),
    }


def _copy_legacy_config(source: AlertmanagerConfig, target: AlertmanagerInstance) -> None:
    for field_name in (
        'endpoint',
        'auth_type',
        'username',
        'password',
        'bearer_token',
        'timeout',
        'verify_ssl',
        'detected_version',
        'compatibility_status',
        'compatibility_profile',
        'capability_profile',
        'readiness_status',
        'validation_message',
        'last_validated_at',
        'last_status',
        'last_error',
        'last_response_time_ms',
        'last_checked_at',
        'created_at',
        'updated_at',
    ):
        setattr(target, field_name, getattr(source, field_name))
    target.enabled = True

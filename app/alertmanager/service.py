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
    AlertmanagerInstanceForm,
    validate_endpoint,
)
from app.alertmanager.repository import (
    get_instance,
    get_instance_by_name,
    list_bindings_for_instance,
    list_instances,
)
from app.alertmanager.resolver import AlertmanagerSourceResolution, resolve_alertmanager_sources
from app.alertmanager.validation import validate_source
from app.extensions import db
from app.integrations.lifecycle import bind_instance, ensure_canonical_instance
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.cluster import Cluster


def get_cluster_by_id(cluster_id: str) -> Cluster | None:
    return db.session.get(Cluster, cluster_id)


def get_alertmanager_instance(instance_id: int) -> AlertmanagerInstance | None:
    return get_instance(instance_id)


def list_alertmanager_instances() -> list[AlertmanagerInstance]:
    return list_instances()


def resolve_alertmanager_scope_sources(
    *,
    scope_type: str,
    scope_key: str,
    required_capabilities: tuple[str, ...] = (),
) -> AlertmanagerSourceResolution:
    return resolve_alertmanager_sources(
        scope_type=scope_type,
        scope_key=scope_key,
        required_capabilities=required_capabilities,
    )


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
    db.session.flush()
    ensure_canonical_instance(instance, provider_type='alertmanager')
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
    if get_alertmanager_bindings(instance.id):
        raise ValueError('Remove all asset bindings before deleting this Alertmanager instance.')
    canonical = (
        db.session.get(IntegrationInstance, instance.integration_instance_id)
        if instance.integration_instance_id
        else None
    )
    db.session.delete(instance)
    if canonical is not None:
        db.session.delete(canonical)
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
) -> IntegrationBinding:
    return create_or_update_binding(instance=instance, form=form, commit=commit)


def remove_alertmanager_binding(binding_id: int) -> IntegrationBinding | None:
    return delete_binding(binding_id)


def get_alertmanager_binding(binding_id: int) -> IntegrationBinding | None:
    from app.alertmanager.repository import get_binding

    return get_binding(binding_id)


def get_alertmanager_bindings(instance_id: int) -> list[IntegrationBinding]:
    return list_bindings_for_instance(instance_id)


def materialize_legacy_cluster_config(cluster_id: str) -> AlertmanagerInstance | None:
    """Compatibility route helper backed only by canonical bindings.

    The historical name is retained until cluster-centric URLs are removed. It no
    longer reads or materializes AlertmanagerConfig records.
    """
    sources = resolve_sources(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)
    return sources[0] if sources else None


def build_alertmanager_client(config: AlertmanagerInstance):
    return build_client(config)


def test_alertmanager_connection(*, cluster_id: str) -> dict[str, Any]:
    sources = resolve_sources(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)
    if not sources:
        return {
            'connected': False,
            'label': 'Alertmanager Not Configured',
            'error': 'No Alertmanager source is bound to this Kubernetes cluster.',
            'reason': 'Integration is not configured',
            'failure_code': 'not_configured',
        }
    return validate_alertmanager_instance(sources[0])


def get_alertmanager_status(*, cluster_id: str) -> dict[str, Any]:
    return get_scope_status(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)


def get_alertmanager_alerts(*, cluster_id: str) -> dict[str, Any]:
    return list_alerts_for_scope(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)


def get_alertmanager_silences(*, cluster_id: str) -> dict[str, Any]:
    return list_silences_for_scope(scope_type=KUBERNETES_CLUSTER_SCOPE, scope_key=cluster_id)


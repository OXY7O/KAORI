from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from sqlalchemy.exc import SQLAlchemyError

from app.alertmanager.bindings import create_or_update_binding, delete_binding, resolve_sources
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
from app.common.integration_errors import describe_integration_failure
from app.extensions.db import db
from app.integrations.alertmanager.exceptions import AlertmanagerError
from app.integrations.deletion import DeletionBlocked, provider_deletion_guard
from app.integrations.lifecycle import ensure_canonical_instance, invalidate_bindings
from app.integrations.registry import get_integration
from app.jobs.service import acquire_resource_admission_locks
from app.models.alertmanager import AlertmanagerInstance
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance


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


def _validate_connection_settings(
    form: AlertmanagerInstanceForm,
    *,
    instance: AlertmanagerInstance | None = None,
) -> None:
    validate_endpoint(form.endpoint)
    if form.auth_type == 'basic':
        if not form.username:
            raise ValueError('Username is required for Basic authentication.')
        if not form.password and (instance is None or not instance.password):
            raise ValueError('Password is required for Basic authentication.')
    if form.auth_type == 'bearer' and not form.bearer_token and (instance is None or not instance.bearer_token):
        raise ValueError('Bearer token is required for Bearer authentication.')


def save_alertmanager_instance(
    *,
    form: AlertmanagerInstanceForm,
    instance: AlertmanagerInstance | None = None,
    commit: bool = True,
) -> AlertmanagerInstance:
    if not form.name:
        raise ValueError('Instance name is required.')
    _validate_connection_settings(form, instance=instance)

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

    # The provider row has a NOT NULL foreign key to IntegrationInstance.
    # Create or resolve the canonical identity before flushing the provider row,
    # otherwise a newly registered Alertmanager is inserted with a NULL
    # integration_instance_id.
    ensure_canonical_instance(instance, provider_type='alertmanager')
    db.session.flush()

    # Refresh canonical metadata after the provider row has received its ID.
    canonical = ensure_canonical_instance(instance, provider_type='alertmanager')
    if not creating:
        invalidate_bindings(
            canonical,
            message=(
                'Alertmanager connection settings changed. Run Full Validation to refresh '
                'the provider and all affected scope bindings.'
            ),
        )
    if commit:
        try:
            db.session.commit()
        except SQLAlchemyError:
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


def validate_alertmanager_binding(
    *,
    instance: AlertmanagerInstance,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    """Validate one scope binding through the canonical provider adapter."""
    return get_integration('alertmanager').execute(
        'binding.validate',
        instance,
        binding=binding,
        commit=commit,
    )


def remove_alertmanager_instance(instance: AlertmanagerInstance) -> None:
    acquire_resource_admission_locks(f'integration:alertmanager:{instance.id}')
    canonical_bindings = get_alertmanager_bindings(instance.id)
    if canonical_bindings:
        raise ValueError(
            'Remove all scope bindings before deleting this Alertmanager instance. '
            f'Canonical bindings: {len(canonical_bindings)}.'
        )

    guard = provider_deletion_guard(
        provider_type='alertmanager',
        provider_instance_id=instance.id,
    )
    if guard.blocked:
        raise DeletionBlocked(guard)

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
    except SQLAlchemyError:
        db.session.rollback()
        raise


def refresh_alertmanager_runtime_health(instance: AlertmanagerInstance) -> dict[str, Any]:
    """Refresh provider health through the canonical registry adapter."""
    return get_integration('alertmanager').execute('runtime.health', instance)


def validate_alertmanager_instance(instance: AlertmanagerInstance) -> dict[str, Any]:
    result = get_integration('alertmanager').execute('runtime.validate', instance)
    return result.to_dict() if hasattr(result, 'to_dict') else dict(result)


def test_alertmanager_form_connection(
    form: AlertmanagerInstanceForm,
    *,
    existing_instance: AlertmanagerInstance | None = None,
) -> dict[str, Any]:
    """Test submitted connection settings without mutating an instance.

    This probe is intentionally limited to the Alertmanager status endpoint. Edit
    forms may reuse the persisted secret when the operator leaves the secret field
    blank and keeps the same authentication type.
    """
    try:
        _validate_connection_settings(form, instance=existing_instance)
    except ValueError as exc:
        return {
            'connected': False,
            'label': 'Connection settings incomplete',
            'error': str(exc),
            'reason': 'Review the submitted endpoint and authentication settings.',
            'failure_code': 'invalid_configuration',
            'request_path': '/api/v2/status',
        }

    password = form.password
    bearer_token = form.bearer_token
    if existing_instance is not None and form.auth_type == existing_instance.auth_type:
        if form.auth_type == 'basic' and not password:
            password = existing_instance.password
        elif form.auth_type == 'bearer' and not bearer_token:
            bearer_token = existing_instance.bearer_token

    draft = AlertmanagerInstance()
    draft.name = 'Connection Test'
    draft.endpoint = form.endpoint
    draft.auth_type = form.auth_type
    draft.username = form.username
    draft.password = password
    draft.bearer_token = bearer_token
    draft.timeout = form.timeout
    draft.verify_ssl = form.verify_ssl
    client = get_integration('alertmanager').execute('client.build', draft)
    try:
        result = client.test_connection()
    except AlertmanagerError as exc:
        failure = describe_integration_failure(
            exc,
            service_name='Alertmanager',
            endpoint=form.endpoint,
            request_path='/api/v2/status',
            timeout_seconds=form.timeout,
        )
        return {
            'connected': False,
            'label': 'Connection failed',
            'error': failure['detail'],
            'reason': failure['reason'],
            'failure_code': failure['code'],
            'endpoint_host': failure['endpoint_host'],
            'endpoint_port': failure['endpoint_port'],
            'request_path': failure['request_path'],
        }
    except Exception as exc:  # pragma: no cover - defensive network boundary
        failure = describe_integration_failure(
            exc,
            service_name='Alertmanager',
            endpoint=form.endpoint,
            request_path='/api/v2/status',
            timeout_seconds=form.timeout,
        )
        return {
            'connected': False,
            'label': 'Connection test failed',
            'error': failure['detail'],
            'reason': failure['reason'],
            'failure_code': failure['code'],
            'endpoint_host': failure['endpoint_host'],
            'endpoint_port': failure['endpoint_port'],
            'request_path': failure['request_path'],
        }

    parsed_endpoint = urlsplit(form.endpoint)
    return {
        'connected': True,
        'label': 'Connection verified',
        'endpoint_host': parsed_endpoint.hostname,
        'endpoint_port': parsed_endpoint.port,
        'response_time_ms': int(result.get('response_time_ms') or 0),
        'version': str(result.get('version') or 'unknown'),
        'cluster_status': str(result.get('cluster_status') or 'unknown'),
        'reason': (
            'The Alertmanager status API responded successfully. Endpoint reachability, '
            'authentication, and TLS negotiation are confirmed for the submitted settings.'
        ),
        'request_path': '/api/v2/status',
    }


def add_alertmanager_binding(
    *,
    instance: AlertmanagerInstance,
    form: AlertmanagerBindingForm,
    commit: bool = True,
) -> IntegrationBinding:
    return create_or_update_binding(instance=instance, form=form, commit=commit)


def update_alertmanager_binding_selector(
    *,
    instance: AlertmanagerInstance,
    binding: IntegrationBinding,
    selector_label: str | None,
    selector_value: str | None,
    selector_operator: str = '=',
    commit: bool = True,
) -> IntegrationBinding:
    return get_integration('alertmanager').execute(
        'binding.selector.update',
        instance,
        binding=binding,
        selector_label=selector_label,
        selector_value=selector_value,
        selector_operator=selector_operator,
        commit=commit,
    )


def remove_alertmanager_binding(binding_id: int) -> IntegrationBinding | None:
    return delete_binding(binding_id)


def get_alertmanager_binding(binding_id: int) -> IntegrationBinding | None:
    from app.alertmanager.repository import get_binding

    return get_binding(binding_id)


def get_alertmanager_bindings(instance_id: int) -> list[IntegrationBinding]:
    return list_bindings_for_instance(instance_id)


def build_alertmanager_client(config: AlertmanagerInstance):
    return get_integration('alertmanager').execute('client.build', config)


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

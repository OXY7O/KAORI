from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from app.alertmanager.bindings import create_or_update_binding, delete_binding, resolve_sources
from app.alertmanager.client import AlertmanagerClient
from app.alertmanager.client_factory import build_client
from app.alertmanager.consumer import (
    KUBERNETES_CLUSTER_SCOPE,
    get_scope_status,
    list_alerts_for_scope,
    list_silences_for_scope,
)
from app.alertmanager.exceptions import AlertmanagerError
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
from app.alertmanager.status import mark_status
from app.common.integration_errors import describe_integration_failure
from app.extensions import db
from app.integrations.binding_selectors import build_selector, selector_filters
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
    if (
        form.auth_type == 'bearer'
        and not form.bearer_token
        and (instance is None or not instance.bearer_token)
    ):
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



def validate_alertmanager_binding(
    *,
    instance: AlertmanagerInstance,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Alertmanager source.')
    filters = list(selector_filters(binding.selector_json))
    if binding.asset_type != 'global' and not filters:
        binding.validation_status = 'blocked'
        binding.validation_message = 'Configure an alert identity selector before validating this binding.'
        binding.last_validated_at = datetime.now(UTC)
        if commit:
            db.session.commit()
        return {'status': binding.validation_status, 'message': binding.validation_message, 'matched_alerts': 0}

    try:
        alerts = build_alertmanager_client(instance).get_alerts(filters=filters)
        binding.validation_status = 'ready'
        binding.validation_message = (
            f'Alertmanager accepted the scope filter and returned {len(alerts)} active alert records.'
        )
        matched = len(alerts)
    except Exception as exc:
        binding.validation_status = 'blocked'
        binding.validation_message = f'Binding validation failed: {exc}'
        matched = 0
    binding.last_validated_at = datetime.now(UTC)
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    return {
        'status': binding.validation_status,
        'message': binding.validation_message,
        'matched_alerts': matched,
    }

def remove_alertmanager_instance(instance: AlertmanagerInstance) -> None:
    if get_alertmanager_bindings(instance.id):
        raise ValueError('Remove all scope bindings before deleting this Alertmanager instance.')
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


def refresh_alertmanager_runtime_health(instance: AlertmanagerInstance) -> dict[str, Any]:
    """Refresh Alertmanager reachability without rebuilding capability evidence."""
    try:
        result = build_client(instance).test_connection()
    except Exception as exc:
        mark_status(
            instance,
            status='disconnected',
            error=str(exc),
            response_time_ms=None,
            commit=True,
        )
        raise
    instance.detected_version = str(result.get('version') or instance.detected_version or 'unknown')
    mark_status(
        instance,
        status='connected',
        error=None,
        response_time_ms=int(result.get('response_time_ms') or 0),
        commit=False,
    )
    if not instance.readiness_status:
        instance.readiness_status = 'validation_required'
        instance.validation_message = (
            'Runtime health is available. Run Full Validation to establish capability evidence.'
        )
    db.session.commit()
    return result


def validate_alertmanager_instance(instance: AlertmanagerInstance) -> dict[str, Any]:
    return validate_source(instance, source_label=instance.name).to_dict()


def test_alertmanager_form_connection(form: AlertmanagerInstanceForm) -> dict[str, Any]:
    """Test draft connection settings without creating or mutating an instance.

    This probe is intentionally limited to the Alertmanager status endpoint. Full
    capability discovery and readiness validation remain a separate post-registration
    workflow.
    """
    try:
        _validate_connection_settings(form)
    except ValueError as exc:
        return {
            'connected': False,
            'label': 'Connection settings incomplete',
            'error': str(exc),
            'reason': 'Review the submitted endpoint and authentication settings.',
            'failure_code': 'invalid_configuration',
            'request_path': '/api/v2/status',
        }

    client = AlertmanagerClient(
        endpoint=form.endpoint,
        auth_type=form.auth_type,
        username=form.username,
        password=form.password,
        bearer_token=form.bearer_token,
        timeout=form.timeout,
        verify_ssl=form.verify_ssl,
    )
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
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Alertmanager source.')
    if binding.asset_type == 'global':
        raise ValueError('Global Alertmanager bindings do not require an alert identity selector.')
    selector_json = build_selector(
        label=selector_label,
        value=selector_value,
        operator=selector_operator,
    )
    if selector_json is None:
        raise ValueError('Define an alert identity selector before saving this binding.')
    binding.selector_json = selector_json
    binding.validation_status = 'validation_required'
    binding.validation_message = (
        'Alert identity changed. Validate this binding before KAORI uses it for operational requests.'
    )
    binding.last_validated_at = None
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    else:
        db.session.flush()
    return binding


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


from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.exc import SQLAlchemyError

from app.common.integration_errors import describe_integration_failure
from app.extensions.db import db
from app.integrations.binding_selectors import build_selector
from app.integrations.deletion import DeletionBlocked, provider_deletion_guard
from app.integrations.lifecycle import bind_instance, ensure_canonical_instance, invalidate_bindings
from app.integrations.prometheus.capabilities import BINDING_CAPABILITY_KEYS
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.registry import get_integration
from app.jobs.service import acquire_resource_admission_locks
from app.models import Cluster, PrometheusInstance
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.forms import PrometheusInstanceForm
from app.prometheus.repository import KUBERNETES_CLUSTER_SCOPE


class PrometheusService:
    """Prometheus domain facade for queries and provider-registry operations.

    Provider validation and compatibility logic is owned by
    ``app.integrations.prometheus``. This facade preserves the established domain
    API for analytics, reports, and routes without duplicating provider behavior.
    """

    def __init__(
        self,
        source: Cluster | PrometheusInstance,
        *,
        cluster: Cluster | None = None,
    ) -> None:
        self.client = None
        if isinstance(source, PrometheusInstance):
            self.cluster = cluster
            self.consumer = PrometheusConsumer(cluster) if cluster is not None else None
            self.instance = self.consumer.config if self.consumer is not None else source
            if self.consumer is None:
                self.client = get_integration('prometheus').execute('client.build', source)
        else:
            self.cluster = source
            self.consumer = PrometheusConsumer(source)
            self.instance = self.consumer.config

    def instant_query(self, query: str) -> dict[str, Any]:
        if self.consumer is not None:
            return self.consumer.query(query)
        if self.client is None:
            raise PrometheusError('Prometheus query client is not available.')
        return self.client.query(query)

    def range_query(
        self,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> dict[str, Any]:
        if self.consumer is not None:
            return self.consumer.query_range(query, start, end, step)
        if self.client is None:
            raise PrometheusError('Prometheus query client is not available.')
        return self.client.query_range(query, start, end, step)

    def test_connection(self, *, persist: bool = True) -> dict[str, Any]:
        return get_integration('prometheus').execute(
            'connection.test',
            self.instance,
            persist=persist,
        )

    def refresh_runtime_health(self) -> dict[str, Any]:
        return get_integration('prometheus').execute('runtime.health', self.instance)

    def validate_integration(self) -> dict[str, Any]:
        return get_integration('prometheus').execute('runtime.validate', self.instance)

    def audit_query_profile(self, *, execute_queries: bool = True) -> dict[str, Any]:
        return get_integration('prometheus').execute(
            'query_profile.audit',
            self.instance,
            execute_queries=execute_queries,
        )


def test_prometheus_form_connection(
    form: PrometheusInstanceForm,
    *,
    existing_instance: PrometheusInstance | None = None,
) -> dict[str, Any]:
    """Test submitted Prometheus settings without mutating the persisted instance.

    Edit forms intentionally leave stored secrets blank. During an update test KAORI
    reuses the saved password or bearer token only when the submitted authentication
    type still matches the persisted contract. A newly supplied secret always wins.
    """
    endpoint = (form.endpoint.data or '').strip()
    auth_type = form.auth_type.data or 'none'
    detection_mode = form.version_detection_mode.data or 'automatic'
    source_major = form.source_prometheus_major.data or None if detection_mode == 'manual' else None
    password = form.password.data or None
    bearer_token = form.bearer_token.data or None
    if existing_instance is not None and auth_type == existing_instance.auth_type:
        if auth_type == 'basic' and not password:
            password = existing_instance.password
        elif auth_type == 'bearer' and not bearer_token:
            bearer_token = existing_instance.bearer_token

    draft = PrometheusInstance()
    draft.name = (form.name.data or '').strip() or 'Draft Prometheus connection'
    draft.endpoint = endpoint
    draft.description = (form.description.data or '').strip() or None
    draft.auth_type = auth_type
    draft.username = (form.username.data or '').strip() or None
    draft.password = password
    draft.bearer_token = bearer_token
    draft.timeout = int(form.timeout.data or 5)
    draft.verify_ssl = bool(form.verify_ssl.data)
    draft.enabled = bool(form.enabled.data)
    draft.version_detection_mode = detection_mode
    draft.endpoint_product = 'thanos' if detection_mode == 'manual' else 'prometheus'
    draft.source_prometheus_major = source_major
    try:
        result = PrometheusService(draft).test_connection(persist=False)
    except Exception as exc:
        failure = describe_integration_failure(
            exc,
            service_name='Prometheus',
            endpoint=endpoint,
            request_path='/api/v1/query',
            timeout_seconds=int(form.timeout.data or 5),
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

    parsed_endpoint = urlsplit(endpoint)
    return {
        'connected': bool(result.get('success')),
        'label': 'Connection verified' if result.get('success') else 'Compatibility blocked',
        'endpoint_host': parsed_endpoint.hostname,
        'endpoint_port': parsed_endpoint.port,
        'response_time_ms': round(float(result.get('response_time') or 0) * 1000),
        'version': str(result.get('endpoint_version') or 'unknown'),
        'endpoint_product': str(result.get('endpoint_product') or 'prometheus'),
        'compatibility_status': result.get('compatibility_status'),
        'compatibility_profile': result.get('compatibility_profile'),
        'reason': result.get('message') or 'The Prometheus query API responded successfully.',
        'error': None if result.get('success') else result.get('message'),
        'failure_code': None if result.get('success') else 'compatibility_blocked',
        'request_path': '/api/v1/query',
    }


def save_prometheus_instance(
    form: PrometheusInstanceForm,
    *,
    instance: PrometheusInstance | None = None,
    initial_cluster: Cluster | None = None,
) -> PrometheusInstance:
    """Create or update a standalone Prometheus runtime and optional cluster binding."""
    endpoint = (form.endpoint.data or '').strip()
    if not endpoint.startswith(('http://', 'https://')):
        raise PrometheusError('Endpoint must start with http:// or https://')

    duplicate = (
        PrometheusInstance.query.join(PrometheusInstance.integration_instance)
        .filter(
            IntegrationInstance.provider_type == 'prometheus',
            IntegrationInstance.name == (form.name.data or '').strip(),
        )
        .first()
    )
    if duplicate is not None and (instance is None or duplicate.id != instance.id):
        raise PrometheusError('A Prometheus instance with this name already exists.')

    creating = instance is None
    if instance is None:
        instance = PrometheusInstance()
        instance.name = (form.name.data or '').strip()
        instance.endpoint = endpoint
        db.session.add(instance)

    instance.name = (form.name.data or '').strip()
    instance.description = (form.description.data or '').strip() or None
    instance.endpoint = endpoint
    instance.auth_type = form.auth_type.data or 'none'
    instance.timeout = form.timeout.data or 5
    instance.verify_ssl = bool(form.verify_ssl.data)
    instance.enabled = bool(form.enabled.data)
    instance.version_detection_mode = form.version_detection_mode.data or 'automatic'
    instance.endpoint_product = 'thanos' if instance.version_detection_mode == 'manual' else 'prometheus'
    instance.source_prometheus_major = (
        (form.source_prometheus_major.data or None) if instance.version_detection_mode == 'manual' else None
    )

    if instance.auth_type == 'basic':
        instance.username = (form.username.data or '').strip() or None
        if form.password.data:
            instance.password = form.password.data
        instance.bearer_token = None
    elif instance.auth_type == 'bearer':
        instance.username = None
        instance.password = None
        if form.bearer_token.data:
            instance.bearer_token = form.bearer_token.data
    else:
        instance.username = None
        instance.password = None
        instance.bearer_token = None

    instance.detected_version = None
    instance.compatibility_status = 'validation_required'
    instance.compatibility_profile = None
    instance.readiness_status = 'validation_required'
    instance.validation_message = 'Configuration changed. Test the endpoint, then run full validation.'
    instance.query_profile = None
    instance.query_validation_status = 'validation_required'
    instance.query_validation_summary = None
    instance.retention_validation_summary = None
    instance.capability_profile = None
    instance.capabilities = None
    instance.module_readiness = None
    instance.last_status = None
    instance.last_error = None
    instance.last_response_time_ms = None
    instance.last_checked_at = None
    instance.last_validated_at = None

    canonical = ensure_canonical_instance(instance, provider_type='prometheus')
    db.session.flush()
    ensure_canonical_instance(instance, provider_type='prometheus')
    if not creating:
        invalidate_bindings(
            canonical,
            message=(
                'Prometheus connection settings changed. Run Full Validation to refresh '
                'the provider and all affected scope bindings.'
            ),
        )
    if initial_cluster is not None:
        bind_instance(
            canonical,
            asset_type=KUBERNETES_CLUSTER_SCOPE,
            asset_key=initial_cluster.id,
            capability_scope=list(BINDING_CAPABILITY_KEYS),
            selector_json=build_selector(label='cluster', value=initial_cluster.name),
            validation_status='validation_required',
            validation_message='Registration created a provisional cluster selector. Verify the actual source label value before operational use.',
        )
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return instance


def validate_prometheus_binding(
    *,
    instance: PrometheusInstance,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    """Validate one scope binding through the canonical provider adapter."""
    return get_integration('prometheus').execute(
        'binding.validate',
        instance,
        binding=binding,
        commit=commit,
    )


def remove_prometheus_instance(instance: PrometheusInstance) -> None:
    """Delete a reusable Prometheus identity after governed dependencies are removed.

    Runtime observation history, canonical JobExecution history, and Activity Audit
    records are intentionally retained. Shared-source bindings and active provider
    jobs must be resolved before the connection identity can be deleted.
    """
    acquire_resource_admission_locks(f'integration:prometheus:{instance.id}')
    canonical_binding_count = 0
    if instance.integration_instance_id is not None:
        canonical_binding_count = IntegrationBinding.query.filter_by(
            integration_instance_id=instance.integration_instance_id,
        ).count()
    if canonical_binding_count:
        raise ValueError(
            'Remove all scope bindings before deleting this Prometheus instance. '
            f'Canonical bindings: {canonical_binding_count}.'
        )

    guard = provider_deletion_guard(
        provider_type='prometheus',
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


def create_prometheus_binding(
    *,
    instance: PrometheusInstance,
    cluster: Cluster,
    role: str = 'primary',
    priority: int = 100,
    selector_label: str | None = None,
    selector_value: str | None = None,
    selector_operator: str = '=',
    commit: bool = True,
) -> IntegrationBinding:
    return get_integration('prometheus').execute(
        'binding.create',
        instance,
        cluster=cluster,
        role=role,
        priority=priority,
        selector_label=selector_label,
        selector_value=selector_value,
        selector_operator=selector_operator,
        commit=commit,
    )


def update_prometheus_binding_selector(
    *,
    instance: PrometheusInstance,
    binding: IntegrationBinding,
    selector_label: str | None,
    selector_value: str | None,
    selector_operator: str = '=',
    commit: bool = True,
) -> IntegrationBinding:
    return get_integration('prometheus').execute(
        'binding.selector.update',
        instance,
        binding=binding,
        selector_label=selector_label,
        selector_value=selector_value,
        selector_operator=selector_operator,
        commit=commit,
    )

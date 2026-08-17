from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.exc import SQLAlchemyError

from app.common.integration_errors import describe_integration_failure
from app.extensions.db import db
from app.integrations.binding_selectors import build_selector
from app.integrations.binding_service import SourceBindingSpec
from app.integrations.deletion import DeletionBlocked, provider_deletion_guard
from app.integrations.lifecycle import (
    BindingPersistenceSpec,
    bind_instance,
    ensure_canonical_instance,
    invalidate_bindings,
)
from app.integrations.metrics.backend_registry import metrics_backend_request_path
from app.integrations.metrics.binding_profiles import get_binding_validation_profile
from app.integrations.metrics.capabilities import BINDING_CAPABILITY_KEYS
from app.integrations.metrics.exceptions import MetricsSourceError
from app.integrations.metrics.providers import provider_definition
from app.integrations.registry import get_integration
from app.jobs.service import acquire_resource_admission_locks
from app.models import Cluster, MetricsSource
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.metrics.consumer import MetricsConsumer
from app.metrics.contracts import MetricsSourceConfigurationInput
from app.metrics.repository import KUBERNETES_CLUSTER_SCOPE


class MetricsService:
    """Provider-neutral query and lifecycle boundary for registered metrics sources."""

    def __init__(
        self,
        source: Cluster | MetricsSource,
        *,
        cluster: Cluster | None = None,
    ) -> None:
        if isinstance(source, MetricsSource):
            self.cluster = cluster
            self.consumer = MetricsConsumer(cluster) if cluster is not None else None
            self.instance = self.consumer.config if self.consumer is not None else source
        else:
            self.cluster = source
            self.consumer = MetricsConsumer(source)
            self.instance = self.consumer.config

    def instant_query(self, query: str) -> dict[str, Any]:
        if self.consumer is not None:
            return self.consumer.query(query)
        return get_integration('metrics_source').execute(
            'query.instant',
            self.instance,
            expression=query,
        )

    def range_query(
        self,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> dict[str, Any]:
        if self.consumer is not None:
            return self.consumer.query_range(query, start, end, step)
        return get_integration('metrics_source').execute(
            'query.range',
            self.instance,
            expression=query,
            start=start,
            end=end,
            step=step,
        )

    def test_connection(self, *, persist: bool = True) -> dict[str, Any]:
        return get_integration('metrics_source').execute(
            'connection.test',
            self.instance,
            persist=persist,
        )

    def refresh_runtime_health(self) -> dict[str, Any]:
        return get_integration('metrics_source').execute('runtime.health', self.instance)

    def validate_integration(self) -> dict[str, Any]:
        return get_integration('metrics_source').execute('runtime.validate', self.instance)

    def audit_query_profile(self, *, execute_queries: bool = True) -> dict[str, Any]:
        return get_integration('metrics_source').execute(
            'query_profile.audit',
            self.instance,
            execute_queries=execute_queries,
        )


def test_metrics_source_connection(
    configuration: MetricsSourceConfigurationInput,
    *,
    existing_instance: MetricsSource | None = None,
) -> dict[str, Any]:
    """Test submitted metrics source settings without mutating persisted state."""
    endpoint = configuration.endpoint.strip()
    auth_type = configuration.auth_type or 'none'
    provider = provider_definition(configuration.provider_key)
    password, bearer_token = _resolved_test_credentials(configuration, existing_instance, auth_type=auth_type)

    draft = MetricsSource()
    draft.name = configuration.name or 'Draft metrics source'
    draft.endpoint = endpoint
    draft.description = configuration.description
    draft.auth_type = auth_type
    draft.username = configuration.username
    draft.password = password
    draft.bearer_token = bearer_token
    draft.timeout = configuration.timeout
    draft.verify_ssl = configuration.verify_ssl
    draft.enabled = configuration.enabled
    draft.provider_key = provider.key
    draft.adapter_key = provider.adapter_key
    draft.query_language = provider.query_language
    draft.version_detection_mode = provider.version_detection_mode
    draft.compatibility_profile_override = configuration.compatibility_profile_override
    draft.endpoint_product = provider.key
    integration = get_integration('metrics_source')
    request_path = metrics_backend_request_path(draft, 'connection.test')
    try:
        result = integration.execute('connection.test', draft, persist=False)
    except Exception as exc:
        failure = describe_integration_failure(
            exc,
            service_name='Metrics Source',
            endpoint=endpoint,
            request_path=request_path,
            timeout_seconds=configuration.timeout,
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
        'endpoint_product': str(result.get('endpoint_product') or provider.key),
        'compatibility_status': result.get('compatibility_status'),
        'compatibility_profile': result.get('compatibility_profile'),
        'reason': result.get('message') or 'The metrics query endpoint responded successfully.',
        'error': None if result.get('success') else result.get('message'),
        'failure_code': None if result.get('success') else 'compatibility_blocked',
        'request_path': request_path,
    }


def _resolved_test_credentials(
    configuration: MetricsSourceConfigurationInput,
    existing_instance: MetricsSource | None,
    *,
    auth_type: str,
) -> tuple[str | None, str | None]:
    password = configuration.password
    bearer_token = configuration.bearer_token
    if existing_instance is None or auth_type != existing_instance.auth_type:
        return password, bearer_token
    if auth_type == 'basic' and not password:
        password = existing_instance.password
    if auth_type == 'bearer' and not bearer_token:
        bearer_token = existing_instance.bearer_token
    return password, bearer_token


def save_metrics_source(
    configuration: MetricsSourceConfigurationInput,
    *,
    instance: MetricsSource | None = None,
    initial_cluster: Cluster | None = None,
) -> MetricsSource:
    """Create or update a reusable metrics source and optional initial asset binding."""
    endpoint = configuration.endpoint.strip()
    if not endpoint.startswith(('http://', 'https://')):
        raise MetricsSourceError('Endpoint must start with http:// or https://')

    duplicate = (
        MetricsSource.query.join(MetricsSource.integration_instance)
        .filter(
            IntegrationInstance.provider_type == 'metrics_source',
            IntegrationInstance.name == configuration.name,
        )
        .first()
    )
    if duplicate is not None and (instance is None or duplicate.id != instance.id):
        raise MetricsSourceError('A metrics source with this name already exists.')

    creating = instance is None
    if instance is None:
        instance = MetricsSource()
        instance.name = configuration.name
        instance.endpoint = endpoint
        db.session.add(instance)

    instance.name = configuration.name
    instance.description = configuration.description
    instance.endpoint = endpoint
    instance.auth_type = configuration.auth_type or 'none'
    instance.timeout = configuration.timeout
    instance.verify_ssl = configuration.verify_ssl
    instance.enabled = configuration.enabled
    _apply_metrics_source_contract(configuration, instance, creating=creating)
    _apply_auth_contract(configuration, instance)
    _reset_provider_evidence(instance)

    canonical = ensure_canonical_instance(instance, provider_type='metrics_source')
    db.session.flush()
    ensure_canonical_instance(instance, provider_type='metrics_source')
    if not creating:
        invalidate_bindings(
            canonical,
            message=(
                'Metrics source settings changed. Run Full Validation to refresh '
                'the provider and all affected scope bindings.'
            ),
        )
    if initial_cluster is not None:
        _bind_initial_cluster(canonical, instance, initial_cluster)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return instance


def _apply_metrics_source_contract(
    configuration: MetricsSourceConfigurationInput,
    instance: MetricsSource,
    *,
    creating: bool,
) -> None:
    provider = provider_definition(configuration.provider_key or instance.provider_key)
    if not creating and instance.provider_key and instance.provider_key != provider.key:
        raise MetricsSourceError(
            'Metrics provider is immutable. Register a separate source when changing provider implementation.'
        )
    instance.provider_key = provider.key
    instance.adapter_key = provider.adapter_key
    instance.query_language = provider.query_language
    instance.version_detection_mode = provider.version_detection_mode
    instance.compatibility_profile_override = configuration.compatibility_profile_override
    instance.endpoint_product = provider.key


def _apply_auth_contract(configuration: MetricsSourceConfigurationInput, instance: MetricsSource) -> None:
    if instance.auth_type == 'basic':
        instance.username = configuration.username
        if configuration.password:
            instance.password = configuration.password
        instance.bearer_token = None
        return
    if instance.auth_type == 'bearer':
        instance.username = None
        instance.password = None
        if configuration.bearer_token:
            instance.bearer_token = configuration.bearer_token
        return
    instance.username = None
    instance.password = None
    instance.bearer_token = None


def _reset_provider_evidence(instance: MetricsSource) -> None:
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


def _bind_initial_cluster(
    canonical: IntegrationInstance,
    instance: MetricsSource,
    initial_cluster: Cluster,
) -> None:
    profile = get_binding_validation_profile(instance.adapter_key, KUBERNETES_CLUSTER_SCOPE)
    bind_instance(
        canonical,
        spec=BindingPersistenceSpec(
            asset_type=KUBERNETES_CLUSTER_SCOPE,
            asset_key=str(initial_cluster.id),
            capability_scope=list(BINDING_CAPABILITY_KEYS),
            selector_json=build_selector(label='cluster', value=initial_cluster.name),
            routing_policy={
                'query_horizon': provider_definition(instance.provider_key).default_query_horizon,
                'weight': 100,
            },
            validation_status='validation_required',
            validation_profile=profile.profile_key if profile is not None else None,
            validation_message=(
                'Registration created a provisional cluster selector. Verify the actual source label value '
                'before operational use.'
            ),
        ),
    )


def validate_metrics_binding(
    *,
    instance: MetricsSource,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    """Validate one scope binding through the canonical provider adapter."""
    return get_integration('metrics_source').execute(
        'binding.validate',
        instance,
        binding=binding,
        commit=commit,
    )


def remove_metrics_source(instance: MetricsSource) -> None:
    """Delete a reusable metrics source identity after governed dependencies are removed.

    Runtime observation history, canonical JobExecution history, and Activity Audit
    records are intentionally retained. Shared-source bindings and active provider
    jobs must be resolved before the connection identity can be deleted.
    """
    acquire_resource_admission_locks(f'integration:metrics_source:{instance.id}')
    canonical_binding_count = 0
    if instance.integration_instance_id is not None:
        canonical_binding_count = IntegrationBinding.query.filter_by(
            integration_instance_id=instance.integration_instance_id,
        ).count()
    if canonical_binding_count:
        raise ValueError(
            'Remove all scope bindings before deleting this metrics source. '
            f'Canonical bindings: {canonical_binding_count}.'
        )

    guard = provider_deletion_guard(
        provider_type='metrics_source',
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


def create_metrics_binding(
    *,
    instance: MetricsSource,
    spec: SourceBindingSpec,
    commit: bool = True,
) -> IntegrationBinding:
    return get_integration('metrics_source').execute(
        'binding.create',
        instance,
        scope_type=spec.asset_type,
        scope_key=spec.asset_key,
        role=spec.role,
        priority=spec.priority,
        selector_label=spec.selector_label,
        selector_value=spec.selector_value,
        selector_operator=spec.selector_operator,
        capability_scope=spec.capability_scope,
        routing_policy=spec.routing_policy,
        enabled=spec.enabled,
        commit=commit,
    )


def update_metrics_binding_selector(
    *,
    instance: MetricsSource,
    binding: IntegrationBinding,
    selector_label: str | None,
    selector_value: str | None,
    selector_operator: str = '=',
    routing_policy: dict | None = None,
    commit: bool = True,
) -> IntegrationBinding:
    return get_integration('metrics_source').execute(
        'binding.selector.update',
        instance,
        binding=binding,
        selector_label=selector_label,
        selector_value=selector_value,
        selector_operator=selector_operator,
        routing_policy=routing_policy,
        commit=commit,
    )

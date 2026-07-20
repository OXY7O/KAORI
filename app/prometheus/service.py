from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from app.common.integration_errors import describe_integration_failure
from app.extensions.db import db
from app.integrations.compatibility import (
    CompatibilityProfile,
    CompatibilityResult,
    evaluate_compatibility,
    get_profile,
)
from app.integrations.binding_selectors import build_selector, selector_is_configured
from app.integrations.lifecycle import bind_instance, ensure_canonical_instance
from app.models import Cluster, PrometheusInstance
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.prometheus.client import PrometheusClient
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.exceptions import PrometheusError
from app.prometheus.forms import PrometheusConfigForm, PrometheusInstanceForm
from app.prometheus.query_profiles.audit import PromQLProfileAuditor
from app.prometheus.repository import KUBERNETES_CLUSTER_SCOPE, resolve_instance_for_cluster


@dataclass(frozen=True)
class PrometheusCompatibilityResolution:
    endpoint_product: str
    endpoint_version: str
    endpoint_compatibility: CompatibilityResult
    endpoint_profile: CompatibilityProfile | None
    source_profile: CompatibilityProfile

    @property
    def query_profile(self) -> str:
        if not self.source_profile.query_profile:
            raise PrometheusError('The selected Prometheus source profile has no PromQL profile.')
        return self.source_profile.query_profile


class PrometheusService:
    def __init__(
        self,
        source: Cluster | PrometheusInstance,
        *,
        cluster: Cluster | None = None,
    ) -> None:
        if isinstance(source, PrometheusInstance):
            config = source
            self.cluster = cluster
        else:
            self.cluster = source
            config = resolve_instance_for_cluster(source.id)
            if not config:
                raise PrometheusError('No Prometheus runtime is bound to the selected Kubernetes cluster')

        self.instance = config
        self.client = PrometheusClient(config)
        self.consumer = PrometheusConsumer(self.cluster) if self.cluster is not None else None

    def instant_query(self, query: str) -> dict[str, Any]:
        if self.consumer is None:
            return self.client.query(query)
        return self.consumer.query(query)

    def range_query(
        self,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> dict[str, Any]:
        if self.consumer is None:
            return self.client.query_range(query, start, end, step)
        return self.consumer.query_range(query, start, end, step)

    def test_connection(self, *, persist: bool = True) -> dict[str, Any]:
        """Run a fast endpoint identity and compatibility check.

        The check proves that the configured query endpoint responds, identifies the
        endpoint runtime, resolves the Prometheus source profile, and selects the
        PromQL contract. Metric, label, query-pack, and retention checks remain part
        of ``validate_integration``. Draft registration probes set ``persist=False``
        so no runtime or readiness state is written before the connection exists.
        """
        started = time.perf_counter()
        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise PrometheusError('Prometheus-compatible query failed')

        resolution = self._resolve_compatibility()
        response_time = time.perf_counter() - started
        if not persist:
            readiness = (
                'blocked'
                if resolution.endpoint_compatibility.readiness == 'blocked'
                else 'degraded'
            )
            message = (
                resolution.endpoint_compatibility.message
                if readiness == 'blocked'
                else (
                    'Endpoint identity and compatibility were verified. Run full validation '
                    'before KAORI marks Kubernetes Analytics as ready.'
                )
            )
            return {
                'success': readiness != 'blocked',
                'endpoint_product': resolution.endpoint_product,
                'endpoint_version': resolution.endpoint_version,
                'version': resolution.endpoint_version,
                'compatibility_status': resolution.endpoint_compatibility.status,
                'readiness_status': readiness,
                'query_profile': resolution.source_profile.query_profile,
                'query_validation_status': 'validation_required',
                'query_validation_summary': None,
                'retention_validation_summary': None,
                'compatibility_profile': resolution.endpoint_compatibility.profile_key,
                'source_prometheus_major': (
                    resolution.source_profile.key.rsplit('v', 1)[-1]
                    if resolution.source_profile.key.startswith('prometheus-http-v')
                    else None
                ),
                'capability_profile': None,
                'capabilities': None,
                'module_readiness': None,
                'message': message,
                'response_time': round(response_time, 3),
            }

        config = self.client.config
        self._store_identity(config, resolution)
        config.query_validation_status = 'validation_required'
        config.query_validation_summary = None
        config.retention_validation_summary = None
        config.last_validated_at = datetime.now(UTC)
        config.last_checked_at = config.last_validated_at
        config.last_response_time_ms = round(response_time * 1000)
        config.last_status = 'connected'
        config.last_error = None

        if resolution.endpoint_compatibility.readiness == 'blocked':
            config.readiness_status = 'blocked'
            config.validation_message = resolution.endpoint_compatibility.message
        else:
            config.readiness_status = 'degraded'
            config.validation_message = (
                'Endpoint identity and compatibility were verified. Run full validation '
                'before KAORI marks Kubernetes Analytics as ready.'
            )
        db.session.commit()

        return self._result_payload(
            config,
            response_time=response_time,
        )

    def refresh_runtime_health(self) -> dict[str, Any]:
        """Refresh endpoint health without discarding capability evidence.

        Scheduled runtime monitoring must stay lightweight. This probe verifies the
        query API and endpoint identity while preserving the latest full-validation
        capability, retention, module-readiness, and query-contract evidence.
        """
        started = time.perf_counter()
        config = self.client.config
        try:
            result = self.client.query('vector(1)')
            if result.get('status') != 'success':
                raise PrometheusError('Prometheus-compatible query failed')

            resolution = self._resolve_compatibility()
            self._store_identity(config, resolution)
            config.last_checked_at = datetime.now(UTC)
            config.last_response_time_ms = round((time.perf_counter() - started) * 1000)
            config.last_status = (
                'incompatible'
                if resolution.endpoint_compatibility.readiness == 'blocked'
                else 'connected'
            )
            config.last_error = None
            if resolution.endpoint_compatibility.readiness == 'blocked':
                config.readiness_status = 'blocked'
                config.validation_message = resolution.endpoint_compatibility.message
            elif not config.readiness_status:
                config.readiness_status = 'validation_required'
                config.validation_message = (
                    'Runtime health is available. Run Full Validation to establish capability evidence.'
                )
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            config = self.client.config
            config.last_checked_at = datetime.now(UTC)
            config.last_response_time_ms = None
            config.last_status = 'disconnected'
            config.last_error = str(exc)[:1000]
            db.session.commit()
            raise

        return self._result_payload(
            config,
            response_time=time.perf_counter() - started,
        )

    def validate_integration(self) -> dict[str, Any]:
        """Run the complete PromQL, metric-schema, and retention validation."""
        started = time.perf_counter()
        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise PrometheusError('Prometheus-compatible query failed')

        resolution = self._resolve_compatibility()
        config = self.client.config
        self._store_identity(config, resolution)

        if resolution.endpoint_compatibility.readiness == 'blocked':
            query_audit = None
            query_status = 'blocked'
            readiness = 'blocked'
        else:
            validation_client = PrometheusClient(
                config,
                request_timeout_seconds=max(int(config.timeout or 5), 30),
            )
            query_audit = PromQLProfileAuditor(validation_client).audit(execute_queries=True)
            contract_summary = query_audit.get('feature_contract_summary') or {}
            query_status = contract_summary.get('status', 'validation_required')
            readiness = resolution.endpoint_compatibility.readiness
            # Runtime compatibility and Analytics readiness are separate. The endpoint can
            # remain connected while one or more exact feature-query contracts are degraded.
            if readiness == 'ready' and query_status != 'ready':
                readiness = 'degraded'

        config.readiness_status = readiness
        config.query_validation_status = query_status
        config.query_validation_summary = (
            {key: value for key, value in query_audit.items() if key not in {'results', 'retention'}}
            if query_audit
            else None
        )
        config.retention_validation_summary = query_audit['retention'] if query_audit else None
        config.capability_profile = query_audit.get('profile') if query_audit else None
        config.capabilities = {
            'available': query_audit.get('available_capabilities', []),
            'assessments': query_audit.get('capability_assessments', []),
        } if query_audit else None
        config.module_readiness = query_audit.get('module_readiness') if query_audit else None
        config.validation_message = self._validation_message(resolution, query_status)
        config.last_validated_at = datetime.now(UTC)
        config.last_checked_at = config.last_validated_at
        config.last_response_time_ms = round((time.perf_counter() - started) * 1000)
        config.last_status = 'connected' if readiness != 'blocked' else 'incompatible'
        config.last_error = None
        db.session.commit()

        return self._result_payload(
            config,
            response_time=time.perf_counter() - started,
        )

    def _resolve_compatibility(self) -> PrometheusCompatibilityResolution:
        config = self.client.config
        detection_mode = config.version_detection_mode or 'automatic'
        build_info = self.client.get_build_info()
        endpoint_version = build_info.get('data', {}).get('version', 'unknown')

        if detection_mode == 'manual':
            source_profile = get_profile('prometheus', f'prometheus-http-v{config.source_prometheus_major}')
            if source_profile is None:
                raise PrometheusError(
                    'Manual mode requires a supported Prometheus source version profile.'
                )
            endpoint_product = 'thanos'
            endpoint_compatibility = evaluate_compatibility(
                endpoint_product,
                endpoint_version,
                capabilities=(
                    'prometheus_api_v1',
                    'instant_query',
                    'range_query',
                    'long_term_history',
                ),
            )
        else:
            endpoint_product = 'prometheus'
            endpoint_compatibility = evaluate_compatibility(
                endpoint_product,
                endpoint_version,
                capabilities=('instant_query', 'range_query'),
            )
            source_profile = get_profile('prometheus', endpoint_compatibility.profile_key)
            if source_profile is None:
                # Unsupported/unknown versions are represented by the endpoint result;
                # use a harmless placeholder only so persistence can complete.
                source_profile = CompatibilityProfile(
                    key='unmatched-prometheus-source',
                    product='prometheus',
                    version_constraint='>=0',
                    support_level='blocked',
                    required_capabilities=(),
                    notes='No supported Prometheus source profile matched.',
                    query_profile=None,
                )

        endpoint_profile = get_profile(endpoint_product, endpoint_compatibility.profile_key)
        return PrometheusCompatibilityResolution(
            endpoint_product=endpoint_product,
            endpoint_version=endpoint_version,
            endpoint_compatibility=endpoint_compatibility,
            endpoint_profile=endpoint_profile,
            source_profile=source_profile,
        )

    @staticmethod
    def _store_identity(
        config: PrometheusInstance,
        resolution: PrometheusCompatibilityResolution,
    ) -> None:
        config.endpoint_product = resolution.endpoint_product
        config.detected_version = resolution.endpoint_version
        config.compatibility_status = resolution.endpoint_compatibility.status
        config.compatibility_profile = resolution.endpoint_compatibility.profile_key
        config.source_prometheus_major = (
            resolution.source_profile.key.rsplit('v', 1)[-1]
            if resolution.source_profile.key.startswith('prometheus-http-v')
            else None
        )
        config.query_profile = resolution.source_profile.query_profile

    @staticmethod
    def _validation_message(
        resolution: PrometheusCompatibilityResolution,
        query_status: str,
    ) -> str:
        if resolution.endpoint_compatibility.readiness == 'blocked':
            return resolution.endpoint_compatibility.message
        if query_status == 'ready':
            return (
                'Endpoint compatibility and every registered Kubernetes Analytics query '
                'contract passed against the configured runtime.'
            )
        return (
            'The Prometheus runtime is connected, but one or more exact Kubernetes '
            'Analytics query contracts require review. Open the observed technical evidence.'
        )

    @staticmethod
    def _result_payload(
        config: PrometheusInstance,
        *,
        response_time: float,
    ) -> dict[str, Any]:
        return {
            'success': config.readiness_status != 'blocked',
            'endpoint_product': config.endpoint_product,
            'endpoint_version': config.detected_version,
            'version': config.detected_version,
            'compatibility_status': config.compatibility_status,
            'readiness_status': config.readiness_status,
            'query_profile': config.query_profile,
            'query_validation_status': config.query_validation_status,
            'query_validation_summary': config.query_validation_summary,
            'retention_validation_summary': config.retention_validation_summary,
            'compatibility_profile': config.compatibility_profile,
            'source_prometheus_major': config.source_prometheus_major,
            'capability_profile': config.capability_profile,
            'capabilities': config.capabilities,
            'module_readiness': config.module_readiness,
            'message': config.validation_message,
            'response_time': round(response_time, 3),
        }

    def audit_query_profile(self, *, execute_queries: bool = True) -> dict[str, Any]:
        audit = PromQLProfileAuditor(self.client).audit(execute_queries=execute_queries)
        config = self.client.config
        config.query_validation_status = 'ready' if audit['blocked_count'] == 0 else 'degraded'
        config.query_validation_summary = {
            key: value for key, value in audit.items() if key not in {'results', 'retention'}
        }
        config.retention_validation_summary = audit['retention']
        db.session.commit()
        return audit

    def _require_runtime_readiness(self) -> None:
        config = self.client.config
        if config.readiness_status in {'blocked', 'validation_required'}:
            raise PrometheusError(
                config.validation_message
                or 'Prometheus integration is not validated for Kubernetes Analytics.'
            )

    @staticmethod
    def save_config(cluster: Cluster, form: PrometheusConfigForm) -> PrometheusInstance:
        config = resolve_instance_for_cluster(cluster.id)
        endpoint = form.endpoint.data
        auth_type = form.auth_type.data
        timeout = form.timeout.data
        verify_ssl = form.verify_ssl.data

        if not endpoint:
            raise PrometheusError('Endpoint is required')
        endpoint = endpoint.strip()
        if not endpoint.startswith(('http://', 'https://')):
            endpoint = f'http://{endpoint}'
        if not auth_type:
            raise PrometheusError('Authentication type is required')
        if timeout is None:
            raise PrometheusError('Timeout is required')

        if not config:
            config = PrometheusInstance(
                name=f'{cluster.name} Prometheus [{cluster.id}]',
                endpoint=endpoint,
            )
            db.session.add(config)
            db.session.flush()

        config.endpoint = endpoint
        config.auth_type = auth_type
        config.timeout = timeout
        config.verify_ssl = verify_ssl

        if auth_type == 'none':
            config.username = None
            config.password = None
            config.bearer_token = None
        elif auth_type == 'basic':
            config.username = form.username.data
            config.password = form.password.data
            config.bearer_token = None
        elif auth_type == 'bearer':
            config.username = None
            config.password = None
            config.bearer_token = form.bearer_token.data

        config.version_detection_mode = form.version_detection_mode.data or 'automatic'
        config.endpoint_product = (
            'thanos' if config.version_detection_mode == 'manual' else 'prometheus'
        )
        config.source_prometheus_major = (
            (form.source_prometheus_major.data or None)
            if config.version_detection_mode == 'manual'
            else None
        )

        config.detected_version = None
        config.compatibility_status = 'validation_required'
        config.readiness_status = 'validation_required'
        config.compatibility_profile = None
        config.query_profile = None
        config.query_validation_status = 'validation_required'
        config.query_validation_summary = None
        config.retention_validation_summary = None
        config.capability_profile = None
        config.capabilities = None
        config.module_readiness = None
        config.last_status = None
        config.last_error = None
        config.last_response_time_ms = None
        config.last_checked_at = None
        config.validation_message = (
            'Configuration changed. Test the endpoint, then run full validation before '
            'KAORI uses it for Kubernetes Analytics.'
        )
        config.last_validated_at = None
        canonical = ensure_canonical_instance(config, provider_type='prometheus')
        bind_instance(
            canonical,
            asset_type=KUBERNETES_CLUSTER_SCOPE,
            asset_key=cluster.id,
            capability_scope=[
                'metrics', 'capacity', 'utilization', 'storage', 'workload',
                'forecast', 'top_consumers', 'alert_metrics',
            ],
        )
        db.session.commit()
        return config


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
    source_major = (
        form.source_prometheus_major.data or None
        if detection_mode == 'manual'
        else None
    )
    password = form.password.data or None
    bearer_token = form.bearer_token.data or None
    if existing_instance is not None and auth_type == existing_instance.auth_type:
        if auth_type == 'basic' and not password:
            password = existing_instance.password
        elif auth_type == 'bearer' and not bearer_token:
            bearer_token = existing_instance.bearer_token

    draft = PrometheusInstance(
        name=(form.name.data or '').strip() or 'Draft Prometheus connection',
        endpoint=endpoint,
        description=(form.description.data or '').strip() or None,
        auth_type=auth_type,
        username=(form.username.data or '').strip() or None,
        password=password,
        bearer_token=bearer_token,
        timeout=int(form.timeout.data or 5),
        verify_ssl=bool(form.verify_ssl.data),
        enabled=bool(form.enabled.data),
        version_detection_mode=detection_mode,
        endpoint_product='thanos' if detection_mode == 'manual' else 'prometheus',
        source_prometheus_major=source_major,
    )
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

    duplicate = PrometheusInstance.query.filter_by(name=(form.name.data or '').strip()).first()
    if duplicate is not None and (instance is None or duplicate.id != instance.id):
        raise PrometheusError('A Prometheus instance with this name already exists.')

    creating = instance is None
    if instance is None:
        instance = PrometheusInstance(name=(form.name.data or '').strip(), endpoint=endpoint)
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
    instance.source_prometheus_major = (form.source_prometheus_major.data or None) if instance.version_detection_mode == 'manual' else None

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
    if initial_cluster is not None:
        bind_instance(
            canonical,
            asset_type=KUBERNETES_CLUSTER_SCOPE,
            asset_key=initial_cluster.id,
            capability_scope=['metrics', 'capacity', 'utilization', 'storage', 'workload', 'forecast', 'top_consumers', 'alert_metrics'],
            selector_json=build_selector(label='cluster', value=initial_cluster.name),
            validation_status='validation_required',
            validation_message='Legacy cluster-assisted registration created a default selector. Verify the actual source label value before use.',
        )
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return instance


def validate_prometheus_binding(
    *,
    instance: PrometheusInstance,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Prometheus source.')
    if not selector_is_configured(binding.selector_json):
        binding.validation_status = 'blocked'
        binding.validation_message = 'Configure a metrics identity selector before validating this binding.'
        binding.last_validated_at = datetime.now(UTC)
        if commit:
            db.session.commit()
        return {'status': binding.validation_status, 'message': binding.validation_message, 'matched_series': 0}

    try:
        payload = PrometheusClient(instance, scope_selector=binding.selector_json).query('count(kube_node_info)')
        if not isinstance(payload, dict) or payload.get('status') != 'success':
            detail = str((payload or {}).get('error') or 'Prometheus returned an unsuccessful query response.') if isinstance(payload, dict) else 'Prometheus returned an invalid query response.'
            raise PrometheusError(detail)
        result = ((payload.get('data') or {}).get('result') or [])
        matched = 0.0
        if result and isinstance(result[0], dict):
            value = result[0].get('value') or []
            if len(value) > 1:
                matched = float(value[1])
        if matched > 0:
            binding.validation_status = 'ready'
            binding.validation_message = f'Metrics identity matched {int(matched)} Kubernetes node series.'
        else:
            binding.validation_status = 'degraded'
            binding.validation_message = 'The selector was accepted, but no kube_node_info series matched this operational scope.'
    except Exception as exc:
        binding.validation_status = 'blocked'
        binding.validation_message = f'Binding validation failed: {exc}'
        matched = 0.0
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
        'matched_series': int(matched),
    }

def remove_prometheus_instance(instance: PrometheusInstance) -> None:
    """Delete a reusable Prometheus identity after governed bindings are removed.

    Runtime observation history and Activity Audit records are intentionally retained.
    The canonical integration identity is removed with the provider record only after
    no provider-neutral scope bindings remain.
    """
    binding_count = 0
    if instance.integration_instance_id is not None:
        binding_count = IntegrationBinding.query.filter_by(
            integration_instance_id=instance.integration_instance_id,
        ).count()
    if binding_count:
        raise ValueError('Remove all scope bindings before deleting this Prometheus instance.')

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



PROMETHEUS_BINDING_CAPABILITIES = [
    'metrics', 'capacity', 'utilization', 'storage', 'workload',
    'forecast', 'top_consumers', 'alert_metrics',
]

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
    normalized_role = str(role or 'primary').strip().lower()
    if normalized_role not in {'primary', 'secondary', 'fallback'}:
        raise ValueError('Select a supported source role.')
    if priority < 1 or priority > 1000:
        raise ValueError('Priority must be between 1 and 1000.')

    selector_json = build_selector(
        label=selector_label,
        value=selector_value,
        operator=selector_operator,
    )
    if selector_json is None:
        raise ValueError('Define a metrics identity selector before binding this Prometheus source.')

    canonical = ensure_canonical_instance(instance, provider_type='prometheus')
    existing = IntegrationBinding.query.filter_by(
        integration_instance_id=canonical.id,
        asset_type=KUBERNETES_CLUSTER_SCOPE,
        asset_key=cluster.id,
    ).first()
    if existing is not None:
        raise ValueError('This Prometheus connection is already bound to the selected managed cluster.')

    if normalized_role == 'primary':
        conflicting_primary = (
            IntegrationBinding.query
            .join(IntegrationInstance, IntegrationBinding.integration_instance_id == IntegrationInstance.id)
            .filter(
                IntegrationInstance.provider_type == 'prometheus',
                IntegrationBinding.asset_type == KUBERNETES_CLUSTER_SCOPE,
                IntegrationBinding.asset_key == cluster.id,
                IntegrationBinding.binding_role == 'primary',
                IntegrationBinding.enabled.is_(True),
            )
            .first()
        )
        if conflicting_primary is not None:
            raise ValueError('The selected managed cluster already has an enabled primary Prometheus source.')

    binding = bind_instance(
        canonical,
        asset_type=KUBERNETES_CLUSTER_SCOPE,
        asset_key=cluster.id,
        role=normalized_role,
        priority=priority,
        capability_scope=PROMETHEUS_BINDING_CAPABILITIES,
        selector_json=selector_json,
        validation_status='validation_required',
        validation_message=(
            'Binding saved. Validate the metrics identity selector and source runtime before operational use.'
        ),
    )
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    else:
        db.session.flush()
    return binding


def update_prometheus_binding_selector(
    *,
    instance: PrometheusInstance,
    binding: IntegrationBinding,
    selector_label: str | None,
    selector_value: str | None,
    selector_operator: str = '=',
    commit: bool = True,
) -> IntegrationBinding:
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Prometheus source.')
    selector_json = build_selector(
        label=selector_label,
        value=selector_value,
        operator=selector_operator,
    )
    if selector_json is None:
        raise ValueError('Define a metrics identity selector before saving this binding.')
    binding.selector_json = selector_json
    binding.validation_status = 'validation_required'
    binding.validation_message = (
        'Metrics identity changed. Validate this binding before KAORI uses it for operational queries.'
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

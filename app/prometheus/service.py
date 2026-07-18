from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.compatibility import (
    CompatibilityProfile,
    CompatibilityResult,
    evaluate_compatibility,
    get_profile,
)
from app.integrations.lifecycle import bind_instance, ensure_canonical_instance
from app.models import Cluster, PrometheusBinding, PrometheusConfig, PrometheusInstance
from app.prometheus.client import PrometheusClient
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.exceptions import PrometheusError
from app.prometheus.forms import PrometheusConfigForm
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
    def __init__(self, cluster: Cluster) -> None:
        self.cluster = cluster
        config = resolve_instance_for_cluster(cluster.id)
        if config is None:
            config = PrometheusConfig.query.filter_by(cluster_id=cluster.id).first()
        if not config:
            raise PrometheusError('No Prometheus runtime is bound to the selected Kubernetes cluster')
        self.client = PrometheusClient(config)
        self.consumer = PrometheusConsumer(cluster)

    def instant_query(self, query: str) -> dict[str, Any]:
        return self.consumer.query(query)

    def range_query(
        self,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> dict[str, Any]:
        return self.consumer.query_range(query, start, end, step)

    def test_connection(self) -> dict[str, Any]:
        """Run a fast endpoint identity and compatibility check.

        The check proves that the configured query endpoint responds, identifies the
        endpoint runtime, resolves the Prometheus source profile, and selects the
        PromQL contract. Metric, label, query-pack, and retention checks remain part
        of ``validate_integration``.
        """
        started = time.perf_counter()
        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise PrometheusError('Prometheus-compatible query failed')

        resolution = self._resolve_compatibility()
        config = self.client.config
        self._store_identity(config, resolution)
        config.query_validation_status = 'validation_required'
        config.query_validation_summary = None
        config.retention_validation_summary = None
        config.last_validated_at = datetime.now(UTC)
        config.last_checked_at = config.last_validated_at
        config.last_response_time_ms = round((time.perf_counter() - started) * 1000)
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
            query_audit = PromQLProfileAuditor(self.client).audit(execute_queries=True)
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
        config: PrometheusConfig,
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
        config: PrometheusConfig,
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
    def save_config(cluster: Cluster, form: PrometheusConfigForm) -> PrometheusConfig:
        config = cluster.prometheus_config
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
            config = PrometheusConfig()
            config.cluster_id = cluster.id
            db.session.add(config)

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
        PrometheusService._sync_runtime_instance(cluster, config)
        db.session.commit()
        return config
    @staticmethod
    def _sync_runtime_instance(cluster: Cluster, config: PrometheusConfig) -> PrometheusInstance:
        """Mirror the legacy cluster form into a standalone runtime plus explicit binding."""
        instance = resolve_instance_for_cluster(cluster.id)
        if instance is None:
            instance = PrometheusInstance(name=f'{cluster.name} Prometheus', endpoint=config.endpoint)
            db.session.add(instance)
            db.session.flush()
            db.session.add(PrometheusBinding(
                prometheus_instance_id=instance.id,
                scope_type=KUBERNETES_CLUSTER_SCOPE,
                scope_key=cluster.id,
                binding_role='primary',
                priority=100,
                enabled=True,
            ))
        fields = (
            'endpoint', 'auth_type', 'username', 'password', 'bearer_token', 'timeout',
            'verify_ssl', 'version_detection_mode', 'endpoint_product', 'source_prometheus_major',
            'detected_version', 'compatibility_status', 'compatibility_profile', 'readiness_status',
            'validation_message', 'last_validated_at', 'query_profile', 'query_validation_status',
            'query_validation_summary', 'retention_validation_summary', 'capability_profile',
            'capabilities', 'module_readiness', 'last_status', 'last_error',
            'last_response_time_ms', 'last_checked_at',
        )
        for field in fields:
            setattr(instance, field, getattr(config, field, None))
        canonical = ensure_canonical_instance(instance, provider_type='prometheus')
        bind_instance(
            canonical,
            asset_type=KUBERNETES_CLUSTER_SCOPE,
            asset_key=cluster.id,
            capability_scope=[
                'metrics', 'capacity', 'utilization', 'storage', 'workload',
                'forecast', 'top_consumers', 'alert_metrics',
            ],
        )
        return instance


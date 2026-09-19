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
    get_profile_by_key,
)
from app.integrations.observability.metrics_source.adapters.prometheus_http.client import PrometheusHttpQueryClient
from app.integrations.observability.metrics_source.adapters.prometheus_http.validation import (
    PROFILE_KEY as CORE_PROFILE_KEY,
)
from app.integrations.observability.metrics_source.adapters.prometheus_http.validation import validate_metrics_core
from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.providers import provider_definition
from app.integrations.observability.metrics_source.query_profiles.audit import PromQLProfileAuditor
from app.models.metrics_source import MetricsSource


@dataclass(frozen=True)
class MetricsCompatibilityResolution:
    endpoint_product: str
    endpoint_version: str
    endpoint_compatibility: CompatibilityResult
    endpoint_profile: CompatibilityProfile | None
    api_profile: CompatibilityProfile | None

    @property
    def query_profile(self) -> str:
        if self.api_profile and self.api_profile.query_profile:
            return self.api_profile.query_profile
        if self.endpoint_profile and self.endpoint_profile.query_profile:
            return self.endpoint_profile.query_profile
        return CORE_PROFILE_KEY


class PrometheusHttpRuntimeService:
    """Runtime workflow for metrics providers using the Prometheus HTTP API."""

    def __init__(self, instance: MetricsSource, *, client: PrometheusHttpQueryClient | None = None) -> None:
        self.instance = instance
        self.client = client or PrometheusHttpQueryClient(instance)

    def test_connection(self, *, persist: bool = True) -> dict[str, Any]:
        started = time.perf_counter()
        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise MetricsSourceError('Metrics query API returned an unsuccessful response.')

        resolution = self._resolve_compatibility()
        response_time = time.perf_counter() - started
        readiness = self._connection_readiness(resolution)
        message = self._connection_message(resolution, readiness)

        if not persist:
            return {
                'success': readiness != 'blocked',
                'endpoint_product': resolution.endpoint_product,
                'endpoint_version': resolution.endpoint_version,
                'version': resolution.endpoint_version,
                'compatibility_status': resolution.endpoint_compatibility.status,
                'readiness_status': readiness,
                'query_profile': resolution.query_profile,
                'query_validation_status': 'validation_required',
                'query_validation_summary': None,
                'retention_validation_summary': None,
                'compatibility_profile': resolution.endpoint_compatibility.profile_key,
                'compatibility_profile_override': self.instance.compatibility_profile_override,
                'capability_profile': None,
                'capabilities': None,
                'module_readiness': None,
                'message': message,
                'response_time': round(response_time, 3),
            }

        config = self.instance
        self._store_identity(config, resolution)
        config.query_validation_status = 'validation_required'
        config.query_validation_summary = None
        config.retention_validation_summary = None
        config.capability_profile = None
        config.capabilities = None
        config.module_readiness = None
        config.last_validated_at = datetime.now(UTC)
        config.last_checked_at = config.last_validated_at
        config.last_response_time_ms = round(response_time * 1000)
        config.last_status = 'incompatible' if readiness == 'blocked' else 'connected'
        config.last_error = None
        config.readiness_status = readiness
        config.validation_message = message
        db.session.commit()
        return self._result_payload(config, response_time=response_time)

    def refresh_health(self) -> dict[str, Any]:
        """Refresh endpoint health without discarding validated capability evidence."""
        started = time.perf_counter()
        config = self.instance
        try:
            result = self.client.query('vector(1)')
            if result.get('status') != 'success':
                raise MetricsSourceError('Metrics query API returned an unsuccessful response.')
            resolution = self._resolve_compatibility()
            self._store_identity(config, resolution)
            config.last_checked_at = datetime.now(UTC)
            config.last_response_time_ms = round((time.perf_counter() - started) * 1000)
            config.last_status = (
                'incompatible' if resolution.endpoint_compatibility.readiness == 'blocked' else 'connected'
            )
            config.last_error = None
            if resolution.endpoint_compatibility.readiness == 'blocked':
                config.readiness_status = 'blocked'
                config.validation_message = resolution.endpoint_compatibility.message
            elif not config.last_validated_at or not config.capability_profile:
                config.readiness_status = (
                    'degraded' if resolution.endpoint_compatibility.readiness == 'degraded' else 'validation_required'
                )
                config.validation_message = (
                    'Runtime health is available. Run Full Validation to establish the metrics query API contract.'
                )
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            config.last_checked_at = datetime.now(UTC)
            config.last_response_time_ms = None
            config.last_status = 'disconnected'
            config.last_error = str(exc)[:1000]
            db.session.commit()
            raise
        return self._result_payload(config, response_time=time.perf_counter() - started)

    def validate(self) -> dict[str, Any]:
        """Validate provider compatibility and the configured metrics query API contract."""
        started = time.perf_counter()
        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise MetricsSourceError('Metrics query API returned an unsuccessful response.')

        resolution = self._resolve_compatibility()
        config = self.instance
        self._store_identity(config, resolution)

        core_audit: dict[str, Any] | None = None
        if resolution.endpoint_compatibility.readiness == 'blocked':
            core_status = 'blocked'
            readiness = 'blocked'
        else:
            validation_client = PrometheusHttpQueryClient(
                config,
                request_timeout_seconds=max(int(config.timeout or 5), 30),
            )
            core_audit = validate_metrics_core(validation_client)
            core_status = str(core_audit.get('status') or 'blocked')
            readiness = 'blocked' if core_status != 'ready' else resolution.endpoint_compatibility.readiness

        config.readiness_status = readiness
        config.query_validation_status = core_status
        config.query_validation_summary = (
            {
                'profile': core_audit.get('profile'),
                'profile_version': core_audit.get('profile_version'),
                'checked_at': core_audit.get('checked_at'),
                'core_summary': core_audit.get('summary'),
                'missing_capabilities': core_audit.get('missing_capabilities', []),
            }
            if core_audit
            else None
        )
        config.retention_validation_summary = None
        config.capability_profile = core_audit.get('profile') if core_audit else None
        config.capabilities = (
            {
                'available': core_audit.get('available_capabilities', []),
                'assessments': core_audit.get('capability_assessments', []),
            }
            if core_audit
            else None
        )
        config.module_readiness = {
            'provider_core': {
                'label': 'Metrics Query API',
                'status': core_status,
                'ready_count': (core_audit or {}).get('summary', {}).get('ready_count', 0),
                'query_count': (core_audit or {}).get('summary', {}).get('total_count', 0),
                'blocked_count': (core_audit or {}).get('summary', {}).get('failed_count', 0),
            }
        }
        config.validation_message = self._validation_message(resolution, core_status)
        config.last_validated_at = datetime.now(UTC)
        config.last_checked_at = config.last_validated_at
        config.last_response_time_ms = round((time.perf_counter() - started) * 1000)
        config.last_status = 'connected' if readiness != 'blocked' else 'incompatible'
        config.last_error = None
        db.session.commit()
        return self._result_payload(config, response_time=time.perf_counter() - started)

    def audit_query_profile(self, *, execute_queries: bool = True) -> dict[str, Any]:
        """Audit the registered PromQL query profile without changing provider readiness."""
        return PromQLProfileAuditor(self.client).audit(execute_queries=execute_queries)

    def _resolve_compatibility(self) -> MetricsCompatibilityResolution:
        config = self.instance
        definition = provider_definition(config.provider_key)
        if definition.adapter_key != 'prometheus_http':
            raise MetricsSourceError(
                f'Metrics provider {definition.label} is not assigned to the Prometheus HTTP adapter.'
            )

        build_info = self.client.get_build_info()
        endpoint_version = build_info.get('data', {}).get('version', 'unknown')
        endpoint_product = definition.key
        endpoint_compatibility = evaluate_compatibility(
            endpoint_product,
            endpoint_version,
            capabilities=definition.endpoint_capabilities,
        )
        endpoint_profile = get_profile(endpoint_product, endpoint_compatibility.profile_key)

        api_profile: CompatibilityProfile | None = endpoint_profile
        if definition.version_detection_mode == 'manual' and config.compatibility_profile_override:
            api_profile = get_profile_by_key(config.compatibility_profile_override)
            if api_profile is None or not api_profile.supports_product(definition.key):
                raise MetricsSourceError(
                    'Configured provider compatibility profile is not supported for this metrics provider.'
                )

        return MetricsCompatibilityResolution(
            endpoint_product=endpoint_product,
            endpoint_version=endpoint_version,
            endpoint_compatibility=endpoint_compatibility,
            endpoint_profile=endpoint_profile,
            api_profile=api_profile,
        )

    @staticmethod
    def _store_identity(config: MetricsSource, resolution: MetricsCompatibilityResolution) -> None:
        config.endpoint_product = resolution.endpoint_product
        config.detected_version = resolution.endpoint_version
        config.compatibility_status = resolution.endpoint_compatibility.status
        config.compatibility_profile = resolution.endpoint_compatibility.profile_key
        config.query_profile = resolution.query_profile

    @staticmethod
    def _connection_readiness(resolution: MetricsCompatibilityResolution) -> str:
        if resolution.endpoint_compatibility.readiness == 'blocked':
            return 'blocked'
        if resolution.endpoint_compatibility.readiness == 'degraded':
            return 'degraded'
        return 'validation_required'

    @staticmethod
    def _connection_message(resolution: MetricsCompatibilityResolution, readiness: str) -> str:
        if readiness == 'blocked':
            return resolution.endpoint_compatibility.message
        if readiness == 'degraded':
            return (
                f'{resolution.endpoint_compatibility.message} Endpoint identity is valid; '
                'run Full Validation to establish the metrics query API contract.'
            )
        return (
            'Endpoint identity and compatibility were verified. Run Full Validation to establish '
            'the metrics query API contract. Consumer metrics remain validated per binding.'
        )

    @staticmethod
    def _validation_message(resolution: MetricsCompatibilityResolution, core_status: str) -> str:
        if resolution.endpoint_compatibility.readiness == 'blocked':
            return resolution.endpoint_compatibility.message
        if core_status != 'ready':
            return (
                'The metrics endpoint responded, but one or more query API capabilities failed. '
                'Review core validation evidence before using this metrics source.'
            )
        if resolution.endpoint_compatibility.readiness == 'degraded':
            return (
                f'{resolution.endpoint_compatibility.message} Metrics query APIs are ready. '
                'Consumer metrics remain governed by asset-scoped bindings.'
            )
        return (
            'Metrics query runtime is ready. Consumer-specific metric contracts are validated independently '
            'through asset-scoped bindings.'
        )

    @staticmethod
    def _result_payload(config: MetricsSource, *, response_time: float) -> dict[str, Any]:
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
            'compatibility_profile_override': config.compatibility_profile_override,
            'capability_profile': config.capability_profile,
            'capabilities': config.capabilities,
            'module_readiness': config.module_readiness,
            'message': config.validation_message,
            'response_time': round(response_time, 3),
        }


def validate_instance(instance: MetricsSource) -> dict[str, Any]:
    return PrometheusHttpRuntimeService(instance).validate()


def refresh_instance_health(instance: MetricsSource) -> dict[str, Any]:
    return PrometheusHttpRuntimeService(instance).refresh_health()

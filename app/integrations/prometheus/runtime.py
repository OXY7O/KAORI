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
from app.integrations.prometheus.client import PrometheusClient
from app.integrations.prometheus.core_validation import PROFILE_KEY as CORE_PROFILE_KEY
from app.integrations.prometheus.core_validation import validate_prometheus_core
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles.audit import PromQLProfileAuditor
from app.models.prometheus import PrometheusInstance


@dataclass(frozen=True)
class PrometheusCompatibilityResolution:
    endpoint_product: str
    endpoint_version: str
    endpoint_compatibility: CompatibilityResult
    endpoint_profile: CompatibilityProfile | None
    source_profile: CompatibilityProfile

    @property
    def query_profile(self) -> str:
        return self.source_profile.query_profile or CORE_PROFILE_KEY


class PrometheusRuntimeService:
    """Canonical provider runtime workflow for Prometheus-compatible sources.

    Provider-level validation is intentionally consumer-neutral. Kubernetes, MinIO,
    and future metric contracts are validated through asset-scoped bindings instead
    of changing the readiness of the shared Prometheus runtime.
    """

    def __init__(
        self,
        instance: PrometheusInstance,
        *,
        client: PrometheusClient | None = None,
    ) -> None:
        self.instance = instance
        self.client = client or PrometheusClient(instance)

    def test_connection(self, *, persist: bool = True) -> dict[str, Any]:
        started = time.perf_counter()
        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise PrometheusError('Prometheus-compatible query failed')

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
                'source_prometheus_major': self._source_major(resolution.source_profile),
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
        """Refresh endpoint health without discarding validated core evidence."""
        started = time.perf_counter()
        config = self.instance
        try:
            result = self.client.query('vector(1)')
            if result.get('status') != 'success':
                raise PrometheusError('Prometheus-compatible query failed')

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
                config.validation_message = 'Runtime health is available. Run Full Validation to establish the provider-level Prometheus core contract.'
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
        """Validate endpoint compatibility and provider-neutral Prometheus core APIs."""
        started = time.perf_counter()
        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise PrometheusError('Prometheus-compatible query failed')

        resolution = self._resolve_compatibility()
        config = self.instance
        self._store_identity(config, resolution)

        core_audit: dict[str, Any] | None = None
        if resolution.endpoint_compatibility.readiness == 'blocked':
            core_status = 'blocked'
            readiness = 'blocked'
        else:
            validation_client = PrometheusClient(
                config,
                request_timeout_seconds=max(int(config.timeout or 5), 30),
            )
            core_audit = validate_prometheus_core(validation_client)
            core_status = str(core_audit.get('status') or 'blocked')
            if core_status != 'ready':
                readiness = 'blocked'
            else:
                readiness = resolution.endpoint_compatibility.readiness

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
                'label': 'Prometheus Core Runtime',
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
        """Return the legacy Kubernetes PromQL audit without changing provider readiness.

        This compatibility entry point remains available for callers that still need
        the Kubernetes query contract during the migration to binding-owned consumer
        validation. It must never downgrade a general Prometheus provider.
        """
        return PromQLProfileAuditor(self.client).audit(execute_queries=execute_queries)

    def _resolve_compatibility(self) -> PrometheusCompatibilityResolution:
        config = self.instance
        detection_mode = config.version_detection_mode or 'automatic'
        build_info = self.client.get_build_info()
        endpoint_version = build_info.get('data', {}).get('version', 'unknown')

        if detection_mode == 'manual':
            source_profile = get_profile('prometheus', f'prometheus-http-v{config.source_prometheus_major}')
            if source_profile is None:
                raise PrometheusError('Manual mode requires a supported Prometheus source version profile.')
            endpoint_product = 'thanos'
            endpoint_compatibility = evaluate_compatibility(
                endpoint_product,
                endpoint_version,
                capabilities=('prometheus_api_v1', 'instant_query', 'range_query', 'long_term_history'),
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
                source_profile = CompatibilityProfile(
                    key='unmatched-prometheus-source',
                    product='prometheus',
                    version_constraint='>=0',
                    support_level='blocked',
                    required_capabilities=(),
                    notes='No supported Prometheus source profile matched.',
                    query_profile=CORE_PROFILE_KEY,
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
    def _source_major(profile: CompatibilityProfile) -> str | None:
        if profile.key.startswith('prometheus-http-v'):
            return profile.key.rsplit('v', 1)[-1]
        return None

    @classmethod
    def _store_identity(
        cls,
        config: PrometheusInstance,
        resolution: PrometheusCompatibilityResolution,
    ) -> None:
        config.endpoint_product = resolution.endpoint_product
        config.detected_version = resolution.endpoint_version
        config.compatibility_status = resolution.endpoint_compatibility.status
        config.compatibility_profile = resolution.endpoint_compatibility.profile_key
        config.source_prometheus_major = cls._source_major(resolution.source_profile)
        config.query_profile = resolution.query_profile

    @staticmethod
    def _connection_readiness(resolution: PrometheusCompatibilityResolution) -> str:
        if resolution.endpoint_compatibility.readiness == 'blocked':
            return 'blocked'
        if resolution.endpoint_compatibility.readiness == 'degraded':
            return 'degraded'
        return 'validation_required'

    @staticmethod
    def _connection_message(resolution: PrometheusCompatibilityResolution, readiness: str) -> str:
        if readiness == 'blocked':
            return resolution.endpoint_compatibility.message
        if readiness == 'degraded':
            return (
                f'{resolution.endpoint_compatibility.message} Endpoint identity is valid; '
                'run Full Validation to establish the provider-level Prometheus core contract.'
            )
        return (
            'Endpoint identity and compatibility were verified. Run Full Validation to establish '
            'the provider-level Prometheus core contract. Kubernetes, MinIO, and other metrics are validated per binding.'
        )

    @staticmethod
    def _validation_message(
        resolution: PrometheusCompatibilityResolution,
        core_status: str,
    ) -> str:
        if resolution.endpoint_compatibility.readiness == 'blocked':
            return resolution.endpoint_compatibility.message
        if core_status != 'ready':
            return (
                'The Prometheus-compatible endpoint responded, but one or more provider-level HTTP/API capabilities failed. '
                'Review the core validation evidence before using this runtime as a metrics source.'
            )
        if resolution.endpoint_compatibility.readiness == 'degraded':
            return (
                f'{resolution.endpoint_compatibility.message} Prometheus core APIs are ready. '
                'Consumer metrics remain governed by asset-scoped bindings.'
            )
        return (
            'Prometheus core runtime is ready. Kubernetes, MinIO, and future metric contracts are validated independently '
            'through their asset-scoped consumer bindings.'
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


def validate_instance(instance: PrometheusInstance) -> dict[str, Any]:
    return PrometheusRuntimeService(instance).validate()


def refresh_instance_health(instance: PrometheusInstance) -> dict[str, Any]:
    return PrometheusRuntimeService(instance).refresh_health()

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
        if not self.source_profile.query_profile:
            raise PrometheusError('The selected Prometheus source profile has no PromQL profile.')
        return self.source_profile.query_profile


class PrometheusRuntimeService:
    """Canonical provider runtime workflow for Prometheus-compatible sources.

    This service owns endpoint compatibility, full PromQL validation, lightweight
    runtime health, and persistence of provider evidence. It intentionally has no
    dependency on the Prometheus web/domain package, so registry adapters can call
    it without creating a reciprocal package dependency.
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
        if not persist:
            readiness = 'blocked' if resolution.endpoint_compatibility.readiness == 'blocked' else 'degraded'
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

        config = self.instance
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

        return self._result_payload(config, response_time=response_time)

    def refresh_health(self) -> dict[str, Any]:
        """Refresh endpoint health without discarding capability evidence."""
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
            elif not config.readiness_status:
                config.readiness_status = 'validation_required'
                config.validation_message = (
                    'Runtime health is available. Run Full Validation to establish capability evidence.'
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

        return self._result_payload(
            config,
            response_time=time.perf_counter() - started,
        )

    def validate(self) -> dict[str, Any]:
        """Run complete PromQL, metric-schema, and retention validation."""
        started = time.perf_counter()
        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise PrometheusError('Prometheus-compatible query failed')

        resolution = self._resolve_compatibility()
        config = self.instance
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
        config.capabilities = (
            {
                'available': query_audit.get('available_capabilities', []),
                'assessments': query_audit.get('capability_assessments', []),
            }
            if query_audit
            else None
        )
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

    def audit_query_profile(self, *, execute_queries: bool = True) -> dict[str, Any]:
        audit = PromQLProfileAuditor(self.client).audit(execute_queries=execute_queries)
        config = self.instance
        config.query_validation_status = 'ready' if audit['blocked_count'] == 0 else 'degraded'
        config.query_validation_summary = {
            key: value for key, value in audit.items() if key not in {'results', 'retention'}
        }
        config.retention_validation_summary = audit['retention']
        db.session.commit()
        return audit

    def _resolve_compatibility(self) -> PrometheusCompatibilityResolution:
        config = self.instance
        detection_mode = config.version_detection_mode or 'automatic'
        build_info = self.client.get_build_info()
        endpoint_version = build_info.get('data', {}).get('version', 'unknown')

        if detection_mode == 'manual':
            source_profile = get_profile(
                'prometheus',
                f'prometheus-http-v{config.source_prometheus_major}',
            )
            if source_profile is None:
                raise PrometheusError('Manual mode requires a supported Prometheus source version profile.')
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


def validate_instance(instance: PrometheusInstance) -> dict[str, Any]:
    return PrometheusRuntimeService(instance).validate()


def refresh_instance_health(instance: PrometheusInstance) -> dict[str, Any]:
    return PrometheusRuntimeService(instance).refresh_health()

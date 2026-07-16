from __future__ import annotations

import time
from typing import Any

from app.extensions.db import db
from app.models import Cluster, PrometheusConfig
from app.prometheus.client import PrometheusClient
from app.prometheus.exceptions import (
    PrometheusError,
)
from app.prometheus.forms import PrometheusConfigForm
from app.integrations.compatibility import evaluate_compatibility, get_profile
from app.prometheus.query_profiles import PROFILE_KEY
from app.prometheus.query_profiles.audit import PromQLProfileAuditor
from datetime import UTC, datetime


class PrometheusService:
    def __init__(
        self,
        cluster: Cluster,
    ) -> None:
        self.cluster = cluster

        config = PrometheusConfig.query.filter_by(
            cluster_id=cluster.id,
        ).first()

        if not config:
            raise PrometheusError('Prometheus configuration not found')

        self.client = PrometheusClient(config)

    def instant_query(
        self,
        query: str,
    ) -> dict[str, Any]:
        self._require_runtime_readiness()
        return self.client.query(query)

    def range_query(
        self,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> dict[str, Any]:
        self._require_runtime_readiness()
        return self.client.query_range(
            query=query,
            start=start,
            end=end,
            step=step,
        )

    def test_connection(
        self,
    ) -> dict[str, Any]:
        """Run a fast endpoint and compatibility check.

        This intentionally avoids metric, label, query-pack, and retention audits so
        the UI connection test completes quickly. Full readiness is handled by
        ``validate_integration``.
        """
        started = time.perf_counter()

        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise PrometheusError('Prometheus query failed')

        version, compatibility, matched_profile = self._resolve_compatibility()
        elapsed = time.perf_counter() - started
        config = self.client.config
        selected_query_profile = (
            matched_profile.query_profile
            if matched_profile and matched_profile.query_profile
            else PROFILE_KEY
        )

        config.detected_version = version
        config.compatibility_status = compatibility.status
        config.compatibility_profile = compatibility.profile_key
        config.query_profile = selected_query_profile
        config.query_validation_status = 'validation_required'
        config.query_validation_summary = None
        config.retention_validation_summary = None
        config.last_validated_at = datetime.now(UTC)

        if compatibility.readiness == 'blocked':
            config.readiness_status = 'blocked'
            config.validation_message = compatibility.message
        else:
            config.readiness_status = 'degraded'
            config.validation_message = (
                'Connection and compatibility profile verified. Run full validation '
                'to check required metrics, label schemas, PromQL, and retention.'
            )

        db.session.commit()

        return {
            'success': compatibility.readiness != 'blocked',
            'version': version,
            'compatibility_status': compatibility.status,
            'readiness_status': config.readiness_status,
            'query_profile': selected_query_profile,
            'query_validation_status': config.query_validation_status,
            'compatibility_profile': compatibility.profile_key,
            'message': config.validation_message,
            'response_time': round(elapsed, 3),
        }

    def validate_integration(
        self,
    ) -> dict[str, Any]:
        """Run the complete compatibility, PromQL, schema, and retention audit."""
        started = time.perf_counter()

        result = self.client.query('vector(1)')
        if result.get('status') != 'success':
            raise PrometheusError('Prometheus query failed')

        version, compatibility, matched_profile = self._resolve_compatibility()
        selected_query_profile = (
            matched_profile.query_profile
            if matched_profile and matched_profile.query_profile
            else PROFILE_KEY
        )

        if compatibility.readiness == 'blocked':
            query_audit = None
            query_status = 'blocked'
            readiness = 'blocked'
        else:
            query_audit = PromQLProfileAuditor(self.client).audit(execute_queries=False)
            query_status = 'ready' if query_audit['blocked_count'] == 0 else 'degraded'
            readiness = compatibility.readiness
            if readiness == 'ready' and query_status == 'degraded':
                readiness = 'degraded'

        config = self.client.config
        config.detected_version = version
        config.compatibility_status = compatibility.status
        config.compatibility_profile = compatibility.profile_key
        config.readiness_status = readiness
        config.query_profile = selected_query_profile
        config.query_validation_status = query_status
        config.query_validation_summary = (
            {key: value for key, value in query_audit.items() if key not in {'results', 'retention'}}
            if query_audit
            else None
        )
        config.retention_validation_summary = query_audit['retention'] if query_audit else None
        config.validation_message = compatibility.message
        config.last_validated_at = datetime.now(UTC)
        db.session.commit()

        return {
            'success': readiness != 'blocked',
            'version': version,
            'compatibility_status': compatibility.status,
            'readiness_status': readiness,
            'query_profile': selected_query_profile,
            'query_validation_status': query_status,
            'query_validation_summary': config.query_validation_summary,
            'retention_validation_summary': config.retention_validation_summary,
            'compatibility_profile': compatibility.profile_key,
            'message': compatibility.message,
            'response_time': round(time.perf_counter() - started, 3),
        }

    def _resolve_compatibility(self):
        detection_mode = self.client.config.version_detection_mode or 'automatic'

        if detection_mode == 'manual':
            selected_profile_key = self.client.config.manual_compatibility_profile
            matched_profile = get_profile('prometheus', selected_profile_key)
            if matched_profile is None:
                raise PrometheusError(
                    'Manual compatibility mode requires a supported Prometheus major-version profile.'
                )

            representative_version = (
                '2.40.0'
                if selected_profile_key == 'prometheus-v2-kubernetes-v1'
                else '3.0.0'
            )
            compatibility = evaluate_compatibility(
                'prometheus',
                representative_version,
                capabilities=('instant_query', 'range_query'),
            )
            version = f"Manual: {'2.x' if representative_version.startswith('2.') else '3.x'}"
            return version, compatibility, matched_profile

        build_info = self.client.get_build_info()
        version = build_info.get('data', {}).get('version', 'unknown')
        compatibility = evaluate_compatibility(
            'prometheus',
            version,
            capabilities=('build_info', 'instant_query', 'range_query'),
        )
        matched_profile = get_profile('prometheus', compatibility.profile_key)
        return version, compatibility, matched_profile

    def audit_query_profile(self, *, execute_queries: bool = True) -> dict[str, Any]:
        audit = PromQLProfileAuditor(self.client).audit(execute_queries=execute_queries)
        config = self.client.config
        config.query_profile = PROFILE_KEY
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
                or 'Prometheus integration is not validated for runtime use.'
            )

    @staticmethod
    def save_config(
        cluster: Cluster,
        form: PrometheusConfigForm,
    ) -> PrometheusConfig:
        config = cluster.prometheus_config

        endpoint = form.endpoint.data
        auth_type = form.auth_type.data
        timeout = form.timeout.data
        verify_ssl = form.verify_ssl.data

        if not endpoint:
            raise PrometheusError('Endpoint is required')

        endpoint = endpoint.strip()

        if not endpoint.startswith(
            (
                'http://',
                'https://',
            )
        ):
            endpoint = f'http://{endpoint}'

        if not auth_type:
            raise PrometheusError('Authentication type is required')

        if timeout is None:
            raise PrometheusError('Timeout is required')

        if not config:
            config = PrometheusConfig()

            config.cluster_id = cluster.id
            config.endpoint = endpoint
            config.auth_type = auth_type
            config.timeout = timeout
            config.verify_ssl = verify_ssl

            db.session.add(config)

        else:
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
        config.manual_compatibility_profile = (form.manual_compatibility_profile.data or None) if config.version_detection_mode == 'manual' else None

        config.detected_version = None
        config.compatibility_status = 'validation_required'
        config.readiness_status = 'validation_required'
        config.compatibility_profile = None
        config.query_profile = None
        config.query_validation_status = 'validation_required'
        config.query_validation_summary = None
        config.retention_validation_summary = None
        config.validation_message = 'Configuration changed. Run validation before KAORI uses this integration.'
        config.last_validated_at = None
        db.session.commit()

        return config

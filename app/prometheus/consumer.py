from __future__ import annotations

import logging
from hashlib import sha256
from time import perf_counter, sleep
from typing import Any

from flask import current_app, has_app_context

from app.common.provider_query_runtime import record_provider_query, record_provider_retry
from app.integrations.consumer.contracts import ConsumerDiagnostic, ConsumerResult, ConsumerSource
from app.integrations.prometheus.exceptions import (
    PrometheusConnectionError,
    PrometheusError,
    PrometheusQueryError,
)
from app.integrations.prometheus.routing import query_horizon_for_range, query_horizon_for_timestamp
from app.integrations.registry import get_integration
from app.models import Cluster
from app.prometheus.resolver import ResolvedPrometheusSource, resolve_prometheus_sources

DEFAULT_QUERY_CAPABILITIES = ('instant_query',)
DEFAULT_RANGE_CAPABILITIES = ('range_query',)
_EXECUTION_CAPABILITIES = frozenset((*DEFAULT_QUERY_CAPABILITIES, *DEFAULT_RANGE_CAPABILITIES))
_TRANSIENT_HTTP_STATUS_TOKENS = ('http 429', 'http 500', 'http 502', 'http 503', 'http 504')
logger = logging.getLogger(__name__)


class PrometheusConsumer:
    """Canonical read boundary for Prometheus-compatible query endpoints.

    Analytics query paths use this consumer directly or through the canonical
    ``PrometheusService`` domain service. Validation and configuration workflows use
    the provider lifecycle service because they own persistence and evidence updates.
    """

    def __init__(
        self,
        cluster: Cluster | None = None,
        *,
        scope_type: str | None = None,
        scope_key: object | None = None,
        scope_name: str | None = None,
    ) -> None:
        if cluster is not None:
            resolved_scope_type = 'kubernetes_cluster'
            resolved_scope_key = str(cluster.id)
            resolved_scope_name = str(cluster.name)
        else:
            resolved_scope_type = str(scope_type or '').strip()
            resolved_scope_key = str(scope_key or '').strip()
            resolved_scope_name = str(scope_name or resolved_scope_key).strip()
        if not resolved_scope_type or not resolved_scope_key:
            raise ValueError('PrometheusConsumer requires a Kubernetes cluster or an explicit asset scope.')

        self.cluster = cluster
        self.scope_type = resolved_scope_type
        self.scope_key = resolved_scope_key
        self.scope_name = resolved_scope_name or resolved_scope_key
        resolution = resolve_prometheus_sources(
            scope_type=self.scope_type,
            scope_key=self.scope_key,
        )
        selected = resolution.selected
        if selected is None:
            reasons = '; '.join(candidate.decision_reason for candidate in resolution.candidates)
            raise PrometheusError(
                reasons or f'No canonical Prometheus runtime is bound to {self.scope_type} {self.scope_name}.'
            )
        self.config = selected.instance
        self.binding = selected.binding
        self._client_cache: dict[tuple[int, int, int | None], Any] = {}
        self._default_instance_id = selected.instance.id

    @classmethod
    def for_asset(
        cls,
        *,
        scope_type: str,
        scope_key: object,
        scope_name: str | None = None,
    ) -> PrometheusConsumer:
        return cls(
            scope_type=scope_type,
            scope_key=scope_key,
            scope_name=scope_name,
        )

    def query(
        self,
        promql: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_QUERY_CAPABILITIES,
        retry_count: int | None = None,
    ) -> dict[str, Any]:
        source = self._source_for(required_capabilities, query_horizon='recent')
        return self._run_query(
            source=source,
            promql=promql,
            range_query=False,
            operation=lambda client: client.query(promql),
            retry_count=retry_count,
        )

    def query_at(
        self,
        promql: str,
        timestamp: float,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_QUERY_CAPABILITIES,
    ) -> dict[str, Any]:
        source = self._source_for(
            required_capabilities,
            query_horizon=query_horizon_for_timestamp(timestamp),
        )
        return self._run_query(
            source=source,
            promql=promql,
            range_query=False,
            operation=lambda client: client.query_at(promql, timestamp),
        )

    def query_range(
        self,
        promql: str,
        start: str,
        end: str,
        step: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_RANGE_CAPABILITIES,
        retry_count: int | None = None,
    ) -> dict[str, Any]:
        source = self._source_for(
            required_capabilities,
            query_horizon=query_horizon_for_range(start, end),
        )
        return self._run_query(
            source=source,
            promql=promql,
            range_query=True,
            operation=lambda client: client.query_range(promql, start, end, step),
            retry_count=retry_count,
        )

    def execute_query(
        self,
        promql: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_QUERY_CAPABILITIES,
    ) -> ConsumerResult[dict[str, Any]]:
        return self._execute(
            lambda source: self._run_query(
                source=source,
                promql=promql,
                range_query=False,
                operation=lambda client: client.query(promql),
            ),
            required_capabilities=required_capabilities,
            execution_capabilities=DEFAULT_QUERY_CAPABILITIES,
            query_horizon='recent',
        )

    def execute_range_query(
        self,
        promql: str,
        start: str,
        end: str,
        step: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_RANGE_CAPABILITIES,
    ) -> ConsumerResult[dict[str, Any]]:
        return self._execute(
            lambda source: self._run_query(
                source=source,
                promql=promql,
                range_query=True,
                operation=lambda client: client.query_range(promql, start, end, step),
            ),
            required_capabilities=required_capabilities,
            execution_capabilities=DEFAULT_RANGE_CAPABILITIES,
            query_horizon=query_horizon_for_range(start, end),
        )

    def requirements(
        self,
        required_capabilities: tuple[str, ...],
    ) -> ConsumerResult[dict[str, Any]]:
        """Evaluate the bounded execution contract for an analytics query.

        Operational Domain Readiness remains the authoritative place for full
        metric, identity, and label evidence. Runtime analytics must only be
        hard-blocked when the Prometheus transport cannot execute the required
        instant or range operation. Missing domain evidence is returned as
        advisory metadata so the worker can run the exact query and collect
        authoritative evidence.
        """
        execution_capabilities = self._execution_capabilities(required_capabilities)
        try:
            selected = self._source_for(execution_capabilities)
        except PrometheusError as exc:
            return ConsumerResult(
                ok=False,
                payload={
                    'readiness': self.config.readiness_status,
                    'missing_capabilities': list(execution_capabilities),
                    'advisory_missing_capabilities': list(self._missing_capabilities(required_capabilities)),
                },
                source=self._source(),
                diagnostics=(
                    ConsumerDiagnostic(
                        code='query_transport_requirements_not_satisfied',
                        message='No bound Prometheus source can execute the required analytics query.',
                        category='capability',
                        remediation='Restore instant or range query capability, then retry materialization.',
                        source_owner='Prometheus / Thanos metrics pipeline',
                        detail=str(exc),
                    ),
                ),
                required_capabilities=required_capabilities,
            )
        return ConsumerResult(
            ok=True,
            payload={
                'readiness': selected.instance.readiness_status,
                'missing_capabilities': [],
                'advisory_missing_capabilities': list(self._missing_capabilities(required_capabilities)),
            },
            source=self._source_from(selected),
            required_capabilities=required_capabilities,
        )

    def status(self) -> ConsumerResult[dict[str, Any]]:
        configured = bool(self.config.endpoint)
        source = self._source()
        last_status = str(self.config.last_status or '').strip().lower()
        runtime_unhealthy = last_status in {'unhealthy', 'error', 'failed', 'disconnected'}
        diagnostics: tuple[ConsumerDiagnostic, ...] = ()
        if not configured:
            diagnostics = (
                ConsumerDiagnostic(
                    code='not_configured',
                    message='Prometheus-compatible endpoint is not configured.',
                    category='configuration',
                    remediation='Configure Prometheus or Thanos Query in Integrations.',
                    source_owner='KAORI Prometheus integration',
                ),
            )
        elif runtime_unhealthy:
            diagnostics = (
                ConsumerDiagnostic(
                    code='runtime_unhealthy',
                    message=(self.config.last_error or 'The latest Prometheus runtime observation is unhealthy.'),
                    category='provider_runtime',
                    remediation='Review Runtime Health, restore connectivity, then retry materialization.',
                    source_owner='Prometheus / Thanos metrics pipeline',
                ),
            )
        return ConsumerResult(
            ok=configured and not runtime_unhealthy,
            payload={
                'configured': configured,
                'readiness': self.config.readiness_status,
                'last_status': self.config.last_status,
                'last_error': self.config.last_error,
                'last_checked_at': self.config.last_checked_at,
                'response_time_ms': self.config.last_response_time_ms,
            },
            source=source,
            diagnostics=diagnostics,
            metadata={
                'readiness_advisory': self.config.readiness_status,
            },
        )

    def analytics_status(self) -> ConsumerResult[dict[str, Any]]:
        """Return execution readiness without issuing a duplicate health query.

        The dataset's real PromQL request is the authoritative runtime probe. A
        stale or failed integration observation remains advisory here so a
        transient previous timeout cannot block an otherwise eligible source.
        """
        try:
            selected = self._source_for(DEFAULT_QUERY_CAPABILITIES)
        except PrometheusError as exc:
            return ConsumerResult(
                ok=False,
                payload={
                    'configured': bool(getattr(self.config, 'endpoint', None)),
                    'last_status': getattr(self.config, 'last_status', None),
                    'last_error': getattr(self.config, 'last_error', None),
                    'last_checked_at': getattr(self.config, 'last_checked_at', None),
                    'response_time_ms': getattr(self.config, 'last_response_time_ms', None),
                },
                source=self._source(),
                diagnostics=(
                    ConsumerDiagnostic(
                        code='analytics_source_not_eligible',
                        message='No bound Prometheus source can execute analytics queries.',
                        category='capability',
                        remediation='Run binding/full validation and restore instant query capability.',
                        source_owner='Prometheus / Thanos metrics pipeline',
                        detail=str(exc),
                    ),
                ),
                required_capabilities=DEFAULT_QUERY_CAPABILITIES,
            )

        observed_health = str(selected.instance.last_status or '').strip().lower()
        observation_degraded = observed_health in {
            'unhealthy',
            'error',
            'failed',
            'disconnected',
        }
        return ConsumerResult(
            ok=True,
            payload={
                'configured': True,
                'readiness': selected.instance.readiness_status,
                'last_status': selected.instance.last_status,
                'last_error': selected.instance.last_error,
                'last_checked_at': selected.instance.last_checked_at,
                'response_time_ms': selected.instance.last_response_time_ms,
                'observation_degraded': observation_degraded,
                'decision_reason': selected.decision_reason,
            },
            source=self._source_from(selected),
            metadata={
                'runtime_observation_advisory': True,
                'observation_degraded': observation_degraded,
            },
            required_capabilities=DEFAULT_QUERY_CAPABILITIES,
        )

    def _run_query(
        self,
        *,
        source: ResolvedPrometheusSource,
        promql: str,
        range_query: bool,
        operation,
        retry_count: int | None = None,
    ) -> dict[str, Any]:
        retries = self._normalize_retry_count(retry_count)
        fingerprint = sha256(promql.encode('utf-8')).hexdigest()[:12]
        operation_name = 'range' if range_query else 'instant'
        timeout_seconds = self._query_timeout_seconds(range_query=range_query)

        for attempt in range(retries + 1):
            started = perf_counter()
            try:
                payload = operation(
                    self._client_for(
                        source,
                        request_timeout_seconds=timeout_seconds,
                    )
                )
            except PrometheusError as exc:
                elapsed_ms = max(int((perf_counter() - started) * 1000), 0)
                record_provider_query(
                    fingerprint=fingerprint,
                    duration_ms=elapsed_ms,
                    success=False,
                    error=exc,
                )
                can_retry = self._is_transient_query_error(exc) and attempt < retries
                if can_retry:
                    record_provider_retry()
                    delay = self._retry_backoff_seconds(attempt + 1)
                    logger.warning(
                        'Transient Prometheus %s query failed; retrying.',
                        operation_name,
                        extra={
                            'scope_type': self.scope_type,
                            'scope_key': self.scope_key,
                            'prometheus_instance_id': source.instance.id,
                            'query_fingerprint': fingerprint,
                            'attempt': attempt + 1,
                            'max_attempts': retries + 1,
                            'retry_delay_seconds': delay,
                            'error': str(exc)[:1000],
                        },
                    )
                    sleep(delay)
                    continue
                logger.error(
                    'Prometheus %s query failed after %s attempt(s).',
                    operation_name,
                    attempt + 1,
                    extra={
                        'scope_type': self.scope_type,
                        'scope_key': self.scope_key,
                        'prometheus_instance_id': source.instance.id,
                        'query_fingerprint': fingerprint,
                        'attempts': attempt + 1,
                        'timeout_seconds': timeout_seconds,
                        'error': str(exc)[:1000],
                    },
                )
                raise
            elapsed_ms = max(int((perf_counter() - started) * 1000), 0)
            record_provider_query(
                fingerprint=fingerprint,
                duration_ms=elapsed_ms,
                success=True,
            )
            return payload
        raise PrometheusConnectionError('Prometheus query retry loop ended unexpectedly.')

    @staticmethod
    def _is_transient_query_error(error: PrometheusError) -> bool:
        if isinstance(error, PrometheusConnectionError):
            return True
        if isinstance(error, PrometheusQueryError):
            message = str(error).lower()
            return any(token in message for token in _TRANSIENT_HTTP_STATUS_TOKENS)
        return False

    @classmethod
    def _normalize_retry_count(cls, retry_count: int | None) -> int:
        if retry_count is None:
            return cls._query_retry_count()
        try:
            return min(max(int(retry_count), 0), 5)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _query_retry_count() -> int:
        if not has_app_context():
            return 0
        try:
            return min(
                max(int(current_app.config.get('PROMETHEUS_ANALYTICS_QUERY_RETRIES', 2)), 0),
                5,
            )
        except (TypeError, ValueError):
            return 2

    @staticmethod
    def _retry_backoff_seconds(attempt: int) -> float:
        if not has_app_context():
            return 0.0
        try:
            base = max(
                float(current_app.config.get('PROMETHEUS_ANALYTICS_RETRY_BACKOFF_SECONDS', 1.0)),
                0.0,
            )
        except (TypeError, ValueError):
            base = 1.0
        return min(base * (2 ** max(attempt - 1, 0)), 10.0)

    def _execute(
        self,
        operation,
        *,
        required_capabilities: tuple[str, ...],
        execution_capabilities: tuple[str, ...],
        query_horizon: str = 'balanced',
    ) -> ConsumerResult[dict[str, Any]]:
        try:
            selected = self._source_for(execution_capabilities, query_horizon=query_horizon)
            payload = operation(selected)
        except PrometheusError as exc:
            return ConsumerResult(
                ok=False,
                payload={},
                source=self._source(),
                diagnostics=(
                    ConsumerDiagnostic(
                        code='provider_query_failed',
                        message='Prometheus-compatible query could not be completed.',
                        category='provider_runtime',
                        remediation=(
                            'Review Integration Runtime diagnostics and capability remediation '
                            'for the configured Prometheus or Thanos Query endpoint.'
                        ),
                        source_owner='Prometheus / Thanos metrics pipeline',
                        detail=str(exc),
                    ),
                ),
                required_capabilities=required_capabilities,
            )
        return ConsumerResult(
            ok=True,
            payload=payload,
            source=self._source_from(selected),
            required_capabilities=required_capabilities,
        )

    @staticmethod
    def _execution_capabilities(
        required_capabilities: tuple[str, ...],
    ) -> tuple[str, ...]:
        return tuple(capability for capability in required_capabilities if capability in _EXECUTION_CAPABILITIES)

    def _source_for(
        self,
        required_capabilities: tuple[str, ...],
        *,
        query_horizon: str = 'balanced',
    ) -> ResolvedPrometheusSource:
        execution_capabilities = self._execution_capabilities(required_capabilities)
        resolution = resolve_prometheus_sources(
            scope_type=self.scope_type,
            scope_key=self.scope_key,
            required_technical_capabilities=execution_capabilities,
            query_horizon=query_horizon,
        )
        selected = resolution.selected
        if selected is not None:
            return selected
        reasons = '; '.join(candidate.decision_reason for candidate in resolution.candidates)
        labels = ', '.join(execution_capabilities)
        requirement = f' Required capabilities: {labels}.' if labels else ''
        raise PrometheusError(
            (reasons or 'No canonical Prometheus runtime is eligible for this operation.') + requirement
        )

    @staticmethod
    def _query_timeout_seconds(*, range_query: bool) -> int | None:
        if not has_app_context():
            return None
        config_key = (
            'PROMETHEUS_ANALYTICS_RANGE_QUERY_TIMEOUT_SECONDS'
            if range_query
            else 'PROMETHEUS_ANALYTICS_QUERY_TIMEOUT_SECONDS'
        )
        default = 120 if range_query else 30
        return int(current_app.config.get(config_key, default))

    def _client_for(
        self,
        source: ResolvedPrometheusSource,
        *,
        request_timeout_seconds: int | None = None,
    ):
        cache_key = (
            int(source.instance.id),
            int(source.binding.id),
            request_timeout_seconds,
        )
        client = self._client_cache.get(cache_key)
        if client is None:
            client = get_integration('prometheus').execute(
                'client.build',
                source.instance,
                scope_selector=source.binding.selector_json,
                request_timeout_seconds=request_timeout_seconds,
            )
            self._client_cache[cache_key] = client
        return client

    def _require_capabilities(self, required_capabilities: tuple[str, ...]) -> None:
        # Eligibility-only callers do not need to construct or execute a client.
        self._source_for(required_capabilities)

    def _missing_capabilities(self, required: tuple[str, ...]) -> tuple[str, ...]:
        if not required:
            return ()
        capability_data = self.config.capabilities or {}
        available = set(capability_data.get('available') or [])
        assessments = {
            item.get('key'): item.get('status')
            for item in capability_data.get('assessments') or []
            if isinstance(item, dict) and item.get('key')
        }
        missing: list[str] = []
        for capability in required:
            status = assessments.get(capability)
            if capability in available or status == 'available':
                continue
            missing.append(capability)
        return tuple(missing)

    def _source(self) -> ConsumerSource:
        return self._source_from_instance(self.config)

    def _source_from(self, selected: ResolvedPrometheusSource) -> ConsumerSource:
        return self._source_from_instance(selected.instance)

    def _source_from_instance(self, config) -> ConsumerSource:
        return ConsumerSource(
            provider='prometheus',
            instance_id=getattr(config, 'id', None),
            instance_name=getattr(config, 'name', None) or self.scope_name or 'Prometheus',
            endpoint_product=getattr(config, 'endpoint_product', None),
            compatibility_profile=getattr(config, 'compatibility_profile', None),
            capability_profile=getattr(config, 'capability_profile', None),
            readiness=getattr(config, 'readiness_status', None),
            health=getattr(config, 'last_status', None),
            fallback_used=getattr(config, 'id', None) != self._default_instance_id,
        )

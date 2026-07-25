from __future__ import annotations

from typing import Any

from flask import current_app, has_app_context

from app.integrations.consumer.contracts import ConsumerDiagnostic, ConsumerResult, ConsumerSource
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.registry import get_integration
from app.models import Cluster
from app.prometheus.resolver import ResolvedPrometheusSource, resolve_prometheus_sources

DEFAULT_QUERY_CAPABILITIES = ('instant_query',)
DEFAULT_RANGE_CAPABILITIES = ('range_query',)
_EXECUTION_CAPABILITIES = frozenset((*DEFAULT_QUERY_CAPABILITIES, *DEFAULT_RANGE_CAPABILITIES))


class PrometheusConsumer:
    """Canonical read boundary for Prometheus-compatible query endpoints.

    Analytics query paths use this consumer directly or through the canonical
    ``PrometheusService`` domain service. Validation and configuration workflows use
    the provider lifecycle service because they own persistence and evidence updates.
    """

    def __init__(self, cluster: Cluster) -> None:
        self.cluster = cluster
        resolution = resolve_prometheus_sources(
            scope_type='kubernetes_cluster',
            scope_key=cluster.id,
        )
        selected = resolution.selected
        if selected is None:
            reasons = '; '.join(candidate.decision_reason for candidate in resolution.candidates)
            raise PrometheusError(reasons or 'No canonical Prometheus runtime is bound to this Kubernetes cluster.')
        self.config = selected.instance
        self.binding = selected.binding
        self.client = self._build_client(selected)
        self._default_instance_id = selected.instance.id

    def query(
        self,
        promql: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_QUERY_CAPABILITIES,
    ) -> dict[str, Any]:
        source = self._source_for(DEFAULT_QUERY_CAPABILITIES)
        return self._build_client(
            source,
            request_timeout_seconds=self._query_timeout_seconds(range_query=False),
        ).query(promql)

    def query_at(
        self,
        promql: str,
        timestamp: float,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_QUERY_CAPABILITIES,
    ) -> dict[str, Any]:
        source = self._source_for(DEFAULT_QUERY_CAPABILITIES)
        return self._build_client(
            source,
            request_timeout_seconds=self._query_timeout_seconds(range_query=False),
        ).query_at(promql, timestamp)

    def query_range(
        self,
        promql: str,
        start: str,
        end: str,
        step: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_RANGE_CAPABILITIES,
    ) -> dict[str, Any]:
        source = self._source_for(DEFAULT_RANGE_CAPABILITIES)
        return self._build_client(
            source,
            request_timeout_seconds=self._query_timeout_seconds(range_query=True),
        ).query_range(promql, start, end, step)

    def execute_query(
        self,
        promql: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_QUERY_CAPABILITIES,
    ) -> ConsumerResult[dict[str, Any]]:
        return self._execute(
            lambda source: self._build_client(
                source,
                request_timeout_seconds=self._query_timeout_seconds(range_query=False),
            ).query(promql),
            required_capabilities=required_capabilities,
            execution_capabilities=DEFAULT_QUERY_CAPABILITIES,
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
            lambda source: self._build_client(
                source,
                request_timeout_seconds=self._query_timeout_seconds(range_query=True),
            ).query_range(promql, start, end, step),
            required_capabilities=required_capabilities,
            execution_capabilities=DEFAULT_RANGE_CAPABILITIES,
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
                    'advisory_missing_capabilities': list(
                        self._missing_capabilities(required_capabilities)
                    ),
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
                'advisory_missing_capabilities': list(
                    self._missing_capabilities(required_capabilities)
                ),
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
                    message=(
                        self.config.last_error
                        or 'The latest Prometheus runtime observation is unhealthy.'
                    ),
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

    def _execute(
        self,
        operation,
        *,
        required_capabilities: tuple[str, ...],
        execution_capabilities: tuple[str, ...],
    ) -> ConsumerResult[dict[str, Any]]:
        try:
            selected = self._source_for(execution_capabilities)
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
        return tuple(
            capability
            for capability in required_capabilities
            if capability in _EXECUTION_CAPABILITIES
        )

    def _source_for(
        self,
        required_capabilities: tuple[str, ...],
    ) -> ResolvedPrometheusSource:
        execution_capabilities = self._execution_capabilities(required_capabilities)
        resolution = resolve_prometheus_sources(
            scope_type='kubernetes_cluster',
            scope_key=self.cluster.id,
            required_technical_capabilities=execution_capabilities,
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

    def _build_client(
        self,
        source: ResolvedPrometheusSource,
        *,
        request_timeout_seconds: int | None = None,
    ):
        return get_integration('prometheus').execute(
            'client.build',
            source.instance,
            scope_selector=source.binding.selector_json,
            request_timeout_seconds=request_timeout_seconds,
        )

    def _require_capabilities(self, required_capabilities: tuple[str, ...]) -> None:
        # Compatibility boundary for callers that only need eligibility validation.
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
            instance_name=getattr(config, 'name', None) or getattr(self.cluster, 'name', None) or 'Prometheus',
            endpoint_product=getattr(config, 'endpoint_product', None),
            compatibility_profile=getattr(config, 'compatibility_profile', None),
            capability_profile=getattr(config, 'capability_profile', None),
            readiness=getattr(config, 'readiness_status', None),
            health=getattr(config, 'last_status', None),
            fallback_used=getattr(config, 'id', None) != self._default_instance_id,
        )

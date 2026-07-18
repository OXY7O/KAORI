from __future__ import annotations

from typing import Any

from app.integrations.consumer import ConsumerDiagnostic, ConsumerResult, ConsumerSource
from app.models import Cluster
from app.prometheus.client import PrometheusClient
from app.prometheus.exceptions import PrometheusError
from app.prometheus.repository import resolve_instance_for_cluster

DEFAULT_QUERY_CAPABILITIES = ('instant_query',)
DEFAULT_RANGE_CAPABILITIES = ('range_query',)


class PrometheusConsumer:
    """Canonical read facade for Prometheus-compatible query endpoints.

    Analytics code must use this facade, or the compatibility ``PrometheusService``
    wrapper that delegates to it. Validation and configuration workflows continue to
    use the provider service directly.
    """

    def __init__(self, cluster: Cluster) -> None:
        self.cluster = cluster
        config = resolve_instance_for_cluster(cluster.id)
        if config is None:
            raise PrometheusError('No Prometheus runtime is bound to the selected Kubernetes cluster')
        self.config = config
        self.client = PrometheusClient(config)

    def query(
        self,
        promql: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_QUERY_CAPABILITIES,
    ) -> dict[str, Any]:
        self._require_capabilities(required_capabilities)
        return self.client.query(promql)

    def query_at(
        self,
        promql: str,
        timestamp: float,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_QUERY_CAPABILITIES,
    ) -> dict[str, Any]:
        self._require_capabilities(required_capabilities)
        return self.client.query_at(promql, timestamp)

    def query_range(
        self,
        promql: str,
        start: str,
        end: str,
        step: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_RANGE_CAPABILITIES,
    ) -> dict[str, Any]:
        self._require_capabilities(required_capabilities)
        return self.client.query_range(promql, start, end, step)

    def execute_query(
        self,
        promql: str,
        *,
        required_capabilities: tuple[str, ...] = DEFAULT_QUERY_CAPABILITIES,
    ) -> ConsumerResult[dict[str, Any]]:
        return self._execute(
            lambda: self.query(promql, required_capabilities=required_capabilities),
            required_capabilities=required_capabilities,
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
            lambda: self.query_range(
                promql,
                start,
                end,
                step,
                required_capabilities=required_capabilities,
            ),
            required_capabilities=required_capabilities,
        )


    def requirements(
        self,
        required_capabilities: tuple[str, ...],
    ) -> ConsumerResult[dict[str, Any]]:
        """Evaluate a consumer capability contract without executing a query."""
        missing = self._missing_capabilities(required_capabilities)
        diagnostics: list[ConsumerDiagnostic] = []

        if self.config.readiness_status in {'blocked', 'validation_required'}:
            diagnostics.append(
                ConsumerDiagnostic(
                    code='not_ready',
                    message=(
                        self.config.validation_message
                        or 'Prometheus integration is not validated for Kubernetes Analytics.'
                    ),
                    category='readiness',
                    remediation='Run full validation and resolve capability findings.',
                    source_owner='Prometheus / Thanos metrics pipeline',
                )
            )

        if missing:
            diagnostics.append(
                ConsumerDiagnostic(
                    code='capability_requirements_not_satisfied',
                    message='The integration does not satisfy the required analytics capabilities.',
                    category='capability',
                    remediation='Review capability remediation on the Prometheus integration page.',
                    source_owner='Prometheus / Thanos metrics pipeline',
                    detail=', '.join(missing),
                )
            )

        return ConsumerResult(
            ok=not diagnostics,
            payload={
                'readiness': self.config.readiness_status,
                'missing_capabilities': list(missing),
            },
            source=self._source(),
            diagnostics=tuple(diagnostics),
            required_capabilities=required_capabilities,
        )

    def status(self) -> ConsumerResult[dict[str, Any]]:
        missing = self._missing_capabilities(())
        configured = bool(self.config.endpoint)
        source = self._source()
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
        elif self.config.readiness_status in {'blocked', 'validation_required'}:
            diagnostics = (
                ConsumerDiagnostic(
                    code='not_ready',
                    message=(
                        self.config.validation_message
                        or 'Prometheus integration is not validated for analytics.'
                    ),
                    category='readiness',
                    remediation='Run full validation and resolve capability findings.',
                    source_owner='Prometheus / Thanos metrics pipeline',
                ),
            )
        return ConsumerResult(
            ok=configured and not diagnostics and not missing,
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
            metadata={'missing_capabilities': list(missing)},
        )

    def _execute(
        self,
        operation,
        *,
        required_capabilities: tuple[str, ...],
    ) -> ConsumerResult[dict[str, Any]]:
        try:
            payload = operation()
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
            source=self._source(),
            required_capabilities=required_capabilities,
        )

    def _require_capabilities(self, required_capabilities: tuple[str, ...]) -> None:
        if self.config.readiness_status in {'blocked', 'validation_required'}:
            raise PrometheusError(
                self.config.validation_message
                or 'Prometheus integration is not validated for Kubernetes Analytics.'
            )
        missing = self._missing_capabilities(required_capabilities)
        if missing:
            labels = ', '.join(missing)
            raise PrometheusError(
                f'Prometheus capability requirements are not satisfied: {labels}. '
                'Review capability remediation in Integrations.'
            )

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
            # Old/migrated configurations may not have a capability snapshot yet.
            # Readiness remains the compatibility gate until full validation is rerun.
            if status is None and not capability_data:
                continue
            missing.append(capability)
        return tuple(missing)

    def _source(self) -> ConsumerSource:
        return ConsumerSource(
            provider='prometheus',
            instance_id=self.config.id,
            instance_name=f'{self.cluster.name} metrics',
            endpoint_product=self.config.endpoint_product,
            compatibility_profile=self.config.compatibility_profile,
            capability_profile=self.config.capability_profile,
            readiness=self.config.readiness_status,
            health=self.config.last_status,
        )

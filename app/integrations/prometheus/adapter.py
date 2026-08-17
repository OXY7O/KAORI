from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.binding_service import SourceBindingSpec
from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.prometheus.binding_management import (
    create_binding,
    update_binding_selector,
)
from app.integrations.prometheus.binding_validation import validate_binding
from app.integrations.prometheus.client import PrometheusClient
from app.integrations.prometheus.runtime import (
    PrometheusRuntimeService,
    refresh_instance_health,
    validate_instance,
)
from app.integrations.runtime.scoring import calculate_health
from app.models.prometheus import PrometheusInstance


class PrometheusRuntimeAdapter:
    provider = 'prometheus'

    def refresh(self, instance: PrometheusInstance) -> dict[str, Any]:
        return validate_instance(instance)

    def refresh_health(self, instance: PrometheusInstance) -> dict[str, Any]:
        return refresh_instance_health(instance)

    def build_client(
        self,
        instance: PrometheusInstance,
        *,
        scope_selector: dict[str, Any] | None = None,
        request_timeout_seconds: int | None = None,
    ):
        return PrometheusClient(
            instance,
            scope_selector=scope_selector,
            request_timeout_seconds=request_timeout_seconds,
        )

    def execute(self, operation: str, instance: PrometheusInstance, **kwargs: Any):
        if operation == 'client.build':
            return self.build_client(
                instance,
                scope_selector=kwargs.get('scope_selector'),
                request_timeout_seconds=kwargs.get('request_timeout_seconds'),
            )
        if operation == 'connection.test':
            return PrometheusRuntimeService(
                instance,
                client=self.build_client(instance),
            ).test_connection(persist=bool(kwargs.get('persist', True)))
        if operation == 'query_profile.audit':
            return PrometheusRuntimeService(
                instance,
                client=self.build_client(instance),
            ).audit_query_profile(
                execute_queries=bool(kwargs.get('execute_queries', True)),
            )
        if operation == 'runtime.validate':
            return self.refresh(instance)
        if operation == 'runtime.health':
            return self.refresh_health(instance)
        if operation == 'runtime.state':
            return self.get_state(instance, validation_result=kwargs.get('validation_result'))
        if operation == 'binding.create':
            return create_binding(
                instance=instance,
                cluster=kwargs.get('cluster'),
                spec=SourceBindingSpec(
                    asset_type=str(kwargs.get('scope_type') or ''),
                    asset_key=str(kwargs.get('scope_key') or ''),
                    role=str(kwargs.get('role') or 'primary'),
                    priority=int(kwargs.get('priority', 100)),
                    selector_label=kwargs.get('selector_label'),
                    selector_value=kwargs.get('selector_value'),
                    selector_operator=str(kwargs.get('selector_operator') or '='),
                    capability_scope=kwargs.get('capability_scope'),
                    routing_policy=kwargs.get('routing_policy'),
                    enabled=bool(kwargs.get('enabled', True)),
                ),
                commit=bool(kwargs.get('commit', True)),
            )
        if operation == 'binding.selector.update':
            binding = kwargs.get('binding')
            if binding is None:
                raise ValueError('Prometheus binding.selector.update requires a binding.')
            return update_binding_selector(
                instance=instance,
                binding=binding,
                selector_label=kwargs.get('selector_label'),
                selector_value=kwargs.get('selector_value'),
                selector_operator=str(kwargs.get('selector_operator') or '='),
                routing_policy=kwargs.get('routing_policy'),
                commit=bool(kwargs.get('commit', True)),
            )
        if operation == 'binding.validate':
            binding = kwargs.get('binding')
            if binding is None:
                raise ValueError('Prometheus binding.validate requires a binding.')
            return validate_binding(
                instance=instance,
                binding=binding,
                commit=bool(kwargs.get('commit', True)),
            )
        raise ValueError(f'Unsupported Prometheus integration operation: {operation}')

    def get_state(
        self, instance: PrometheusInstance, *, validation_result: dict[str, Any] | None = None
    ) -> RuntimeState:
        now = datetime.now(UTC)
        assessments = (instance.capabilities or {}).get('assessments') or []
        core_summary = (instance.query_validation_summary or {}).get('core_summary') or {}
        diagnostics = self._diagnostics(instance, assessments)
        health = calculate_health(self._factors(instance, assessments, core_summary))
        available = tuple(sorted((instance.capabilities or {}).get('available') or ()))
        snapshot = CapabilitySnapshot(
            profile=instance.capability_profile or instance.query_profile,
            compatibility_profile=instance.compatibility_profile,
            capabilities=available,
            observed_at=instance.last_checked_at or instance.last_validated_at or now,
            metadata={
                'endpoint_product': instance.endpoint_product,
                'metrics_source_type': instance.source_type or 'prometheus',
                'endpoint_version': instance.detected_version,
                'source_prometheus_major': instance.source_prometheus_major,
                'module_readiness': instance.module_readiness or {},
                'capability_assessments': assessments,
                'core_validation_summary': core_summary,
                'consumer_validation_owner': 'integration_binding',
            },
        )
        fallback_name = (
            'Thanos Query metrics source' if instance.source_type == 'thanos' else 'Prometheus metrics source'
        )
        return RuntimeState(
            provider=self.provider,
            instance_id=str(instance.id),
            instance_name=getattr(instance, 'name', None) or fallback_name,
            observed_at=instance.last_checked_at or instance.last_validated_at or now,
            readiness=instance.readiness_status or 'validation_required',
            health=health,
            diagnostics=diagnostics,
            snapshot=snapshot,
            last_success_at=instance.last_checked_at if instance.last_status == 'connected' else None,
            last_failure_at=instance.last_checked_at
            if instance.last_status in {'error', 'disconnected', 'incompatible'}
            else None,
            latency_ms=instance.last_response_time_ms,
            message=instance.validation_message
            or instance.last_error
            or 'Run full validation to observe this metrics source.',
        )

    @staticmethod
    def _diagnostics(instance: PrometheusInstance, assessments: list[dict[str, Any]]) -> tuple[DiagnosticResult, ...]:
        rows = [
            DiagnosticResult(
                key='endpoint',
                label='Metrics endpoint',
                category='connectivity',
                status='success'
                if instance.last_status == 'connected'
                else ('failed' if instance.last_status else 'unknown'),
                detail=(
                    f'{(instance.endpoint_product or "Prometheus").title()} {instance.detected_version or "version not observed"}'
                    if instance.last_status == 'connected'
                    else instance.last_error or 'Endpoint validation has not been observed.'
                ),
                duration_ms=instance.last_response_time_ms,
                severity='critical' if instance.last_status in {'error', 'disconnected'} else 'info',
                recommendation='Review endpoint, authentication, TLS, and reverse proxy access.'
                if instance.last_status in {'error', 'disconnected'}
                else None,
            )
        ]
        for item in assessments:
            if item.get('status') == 'available':
                continue
            rows.append(
                DiagnosticResult(
                    key=item['key'],
                    label=item['label'],
                    category='capability',
                    status='failed' if item.get('status') in {'missing', 'misconfigured', 'unsupported'} else 'warning',
                    detail=item.get('evidence') or item.get('impact') or '',
                    severity='warning',
                    recommendation=item.get('recommendation'),
                )
            )
        return tuple(rows)

    @staticmethod
    def _factors(
        instance: PrometheusInstance,
        assessments: list[dict[str, Any]],
        core_summary: dict[str, Any],
    ) -> tuple[HealthFactor, ...]:
        missing = [item for item in assessments if item.get('status') in {'missing', 'misconfigured', 'unsupported'}]
        capability_score = max(0, round(100 - (len(missing) * 15))) if assessments else 50
        core_status = core_summary.get('status') or instance.query_validation_status
        return (
            HealthFactor(
                'connectivity',
                'Connectivity',
                'success' if instance.last_status == 'connected' else ('failed' if instance.last_status else 'unknown'),
                30,
                100 if instance.last_status == 'connected' else (0 if instance.last_status else 50),
                instance.last_error or '',
            ),
            HealthFactor(
                'readiness',
                'Provider readiness',
                'success'
                if instance.readiness_status == 'ready'
                else ('failed' if instance.readiness_status == 'blocked' else 'warning'),
                25,
                100 if instance.readiness_status == 'ready' else (0 if instance.readiness_status == 'blocked' else 65),
                instance.validation_message or '',
            ),
            HealthFactor(
                'core_contract',
                'Prometheus core APIs',
                'success' if core_status == 'ready' else ('failed' if core_status == 'blocked' else 'warning'),
                25,
                100 if core_status == 'ready' else (0 if core_status == 'blocked' else 65),
                f'{core_summary.get("failed_count", 0)} of {core_summary.get("total_count", 0)} core API checks failed.',
            ),
            HealthFactor(
                'capability',
                'Capability coverage',
                'success' if not missing and assessments else ('warning' if assessments else 'unknown'),
                10,
                capability_score,
                f'{len(missing)} capabilities require attention.',
            ),
            HealthFactor(
                'latency',
                'Latency',
                'warning'
                if (instance.last_response_time_ms or 0) > 1500
                else ('success' if instance.last_response_time_ms is not None else 'unknown'),
                10,
                60
                if (instance.last_response_time_ms or 0) > 1500
                else (100 if instance.last_response_time_ms is not None else 50),
            ),
        )


runtime_adapter = PrometheusRuntimeAdapter()

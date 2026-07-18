from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.runtime.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.runtime.scoring import calculate_health
from app.models.prometheus import PrometheusConfig
from app.prometheus.service import PrometheusService


class PrometheusRuntimeAdapter:
    provider = 'prometheus'

    def refresh(self, instance: PrometheusConfig) -> dict[str, Any]:
        return PrometheusService(instance.cluster).validate_integration()

    def get_state(self, instance: PrometheusConfig, *, validation_result: dict[str, Any] | None = None) -> RuntimeState:
        now = datetime.now(UTC)
        assessments = ((instance.capabilities or {}).get('assessments') or [])
        diagnostics = self._diagnostics(instance, assessments)
        health = calculate_health(self._factors(instance, assessments))
        available = tuple(sorted((instance.capabilities or {}).get('available') or ()))
        snapshot = CapabilitySnapshot(
            profile=instance.capability_profile or instance.query_profile,
            compatibility_profile=instance.compatibility_profile,
            capabilities=available,
            observed_at=instance.last_checked_at or instance.last_validated_at or now,
            metadata={
                'endpoint_product': instance.endpoint_product,
                'endpoint_version': instance.detected_version,
                'source_prometheus_major': instance.source_prometheus_major,
                'module_readiness': instance.module_readiness or {},
                'capability_assessments': assessments,
            },
        )
        return RuntimeState(
            provider=self.provider,
            instance_id=str(instance.id),
            instance_name=f'{instance.cluster.name} metrics',
            observed_at=instance.last_checked_at or instance.last_validated_at or now,
            readiness=instance.readiness_status or 'validation_required',
            health=health,
            diagnostics=diagnostics,
            snapshot=snapshot,
            last_success_at=instance.last_checked_at if instance.last_status == 'connected' else None,
            last_failure_at=instance.last_checked_at if instance.last_status in {'error', 'disconnected', 'incompatible'} else None,
            latency_ms=instance.last_response_time_ms,
            message=instance.validation_message or instance.last_error or 'Run full validation to observe this metrics source.',
        )

    @staticmethod
    def _diagnostics(instance: PrometheusConfig, assessments: list[dict[str, Any]]) -> tuple[DiagnosticResult, ...]:
        rows = [
            DiagnosticResult(
                key='endpoint', label='Metrics endpoint', category='connectivity',
                status='success' if instance.last_status == 'connected' else ('failed' if instance.last_status else 'unknown'),
                detail=(f'{(instance.endpoint_product or "Prometheus").title()} {instance.detected_version or "version not observed"}' if instance.last_status == 'connected' else instance.last_error or 'Endpoint validation has not been observed.'),
                duration_ms=instance.last_response_time_ms,
                severity='critical' if instance.last_status in {'error', 'disconnected'} else 'info',
                recommendation='Review endpoint, authentication, TLS, and reverse proxy access.' if instance.last_status in {'error', 'disconnected'} else None,
            )
        ]
        for item in assessments:
            if item.get('status') == 'available':
                continue
            rows.append(DiagnosticResult(
                key=item['key'], label=item['label'], category='capability',
                status='failed' if item.get('status') in {'missing', 'misconfigured', 'unsupported'} else 'warning',
                detail=item.get('evidence') or item.get('impact') or '',
                severity='warning', recommendation=item.get('recommendation'),
            ))
        return tuple(rows)

    @staticmethod
    def _factors(instance: PrometheusConfig, assessments: list[dict[str, Any]]) -> tuple[HealthFactor, ...]:
        missing = [item for item in assessments if item.get('status') in {'missing', 'misconfigured', 'unsupported'}]
        capability_score = max(0, round(100 - (len(missing) * 15))) if assessments else 50
        return (
            HealthFactor('connectivity', 'Connectivity', 'success' if instance.last_status == 'connected' else ('failed' if instance.last_status else 'unknown'), 30, 100 if instance.last_status == 'connected' else (0 if instance.last_status else 50), instance.last_error or ''),
            HealthFactor('readiness', 'Analytics readiness', 'success' if instance.readiness_status == 'ready' else ('failed' if instance.readiness_status == 'blocked' else 'warning'), 25, 100 if instance.readiness_status == 'ready' else (0 if instance.readiness_status == 'blocked' else 65), instance.validation_message or ''),
            HealthFactor('query_contract', 'PromQL contract', 'success' if instance.query_validation_status == 'ready' else ('failed' if instance.query_validation_status == 'blocked' else 'warning'), 25, 100 if instance.query_validation_status == 'ready' else (0 if instance.query_validation_status == 'blocked' else 65)),
            HealthFactor('capability', 'Capability coverage', 'success' if not missing and assessments else ('warning' if assessments else 'unknown'), 10, capability_score, f'{len(missing)} capabilities require attention.'),
            HealthFactor('latency', 'Latency', 'warning' if (instance.last_response_time_ms or 0) > 1500 else ('success' if instance.last_response_time_ms is not None else 'unknown'), 10, 60 if (instance.last_response_time_ms or 0) > 1500 else (100 if instance.last_response_time_ms is not None else 50)),
        )


runtime_adapter = PrometheusRuntimeAdapter()

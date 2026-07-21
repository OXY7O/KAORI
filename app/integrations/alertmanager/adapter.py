from __future__ import annotations

from datetime import UTC, datetime

from app.integrations.alertmanager.contracts import ValidationResult
from app.integrations.alertmanager.validation import validate_source
from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.runtime.scoring import calculate_health
from app.models.alertmanager import AlertmanagerInstance


class AlertmanagerRuntimeAdapter:
    provider = 'alertmanager'

    def refresh(self, instance: AlertmanagerInstance) -> ValidationResult:
        return validate_source(instance, source_label=instance.name)

    def refresh_health(self, instance: AlertmanagerInstance) -> dict:
        from app.alertmanager.service import refresh_alertmanager_runtime_health

        return refresh_alertmanager_runtime_health(instance)


    def build_client(self, instance: AlertmanagerInstance):
        from app.integrations.alertmanager.client_factory import build_client

        return build_client(instance)

    def execute(self, operation: str, instance: AlertmanagerInstance, **kwargs):
        if operation == 'client.build':
            return self.build_client(instance)
        if operation == 'runtime.validate':
            return self.refresh(instance)
        if operation == 'runtime.health':
            return self.refresh_health(instance)
        if operation == 'runtime.state':
            return self.get_state(instance, validation_result=kwargs.get('validation_result'))
        raise ValueError(f'Unsupported Alertmanager integration operation: {operation}')

    def get_state(self, instance: AlertmanagerInstance, *, validation_result: ValidationResult | None = None) -> RuntimeState:
        now = datetime.now(UTC)
        diagnostics = self._diagnostics(instance, validation_result)
        factors = self._factors(instance, diagnostics)
        health = calculate_health(factors)
        snapshot = CapabilitySnapshot(
            profile=instance.capability_profile,
            compatibility_profile=instance.compatibility_profile,
            capabilities=tuple(sorted(instance.capabilities or ())),
            observed_at=instance.last_checked_at or instance.last_validated_at or now,
            metadata={'version': instance.detected_version, 'compatibility_status': instance.compatibility_status},
        )
        success_at = instance.last_checked_at if instance.last_status == 'connected' else None
        failure_at = instance.last_checked_at if instance.last_status in {'error', 'disconnected', 'incompatible'} else None
        return RuntimeState(
            provider=self.provider,
            instance_id=str(instance.id),
            instance_name=instance.name,
            observed_at=instance.last_checked_at or instance.last_validated_at or now,
            readiness=instance.readiness_status or 'validation_required',
            health=health,
            diagnostics=diagnostics,
            snapshot=snapshot,
            last_success_at=success_at,
            last_failure_at=failure_at,
            latency_ms=instance.last_response_time_ms,
            message=instance.validation_message or instance.last_error or 'Run runtime validation to observe this source.',
        )

    @staticmethod
    def _diagnostics(instance: AlertmanagerInstance, result: ValidationResult | None) -> tuple[DiagnosticResult, ...]:
        if result and result.validation_steps:
            return tuple(DiagnosticResult(
                key=step.key,
                label=step.label,
                category='api' if step.key.endswith('_v2') else 'compatibility',
                status=step.status,
                detail=step.detail,
                duration_ms=step.response_time_ms,
                severity='critical' if step.status == 'failed' else 'info',
                recommendation='Review endpoint, credentials, TLS, and provider logs.' if step.status == 'failed' else None,
            ) for step in result.validation_steps)
        status = 'success' if instance.last_status == 'connected' else ('failed' if instance.last_status in {'error', 'disconnected', 'incompatible'} else 'unknown')
        return (DiagnosticResult('runtime', 'Runtime observation', 'runtime', status, instance.last_error or instance.validation_message or 'Validation has not been observed.'),)

    @staticmethod
    def _factors(instance: AlertmanagerInstance, diagnostics: tuple[DiagnosticResult, ...]) -> tuple[HealthFactor, ...]:
        api_failed = any(row.status == 'failed' and row.category == 'api' for row in diagnostics)
        return (
            HealthFactor('connectivity', 'Connectivity', 'failed' if instance.last_status in {'error', 'disconnected'} else ('success' if instance.last_status == 'connected' else 'unknown'), 30, 0 if instance.last_status in {'error', 'disconnected'} else (100 if instance.last_status == 'connected' else 55), instance.last_error or ''),
            HealthFactor('readiness', 'Readiness', 'failed' if instance.readiness_status == 'blocked' else ('success' if instance.readiness_status == 'ready' else 'warning'), 25, 0 if instance.readiness_status == 'blocked' else (100 if instance.readiness_status == 'ready' else 65), instance.validation_message or ''),
            HealthFactor('api', 'Provider API', 'failed' if api_failed else ('success' if instance.last_status == 'connected' else 'unknown'), 25, 0 if api_failed else (100 if instance.last_status == 'connected' else 55)),
            HealthFactor('capability', 'Capability discovery', 'success' if instance.capabilities else 'unknown', 10, 100 if instance.capabilities else 50),
            HealthFactor('latency', 'Latency', 'warning' if (instance.last_response_time_ms or 0) > 1500 else ('success' if instance.last_response_time_ms is not None else 'unknown'), 10, 60 if (instance.last_response_time_ms or 0) > 1500 else (100 if instance.last_response_time_ms is not None else 50)),
        )


runtime_adapter = AlertmanagerRuntimeAdapter()

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.integrations.registry.providers.harbor.contracts import ValidationResult
from app.integrations.registry.providers.harbor.runtime import refresh_instance_health
from app.integrations.registry.providers.harbor.validation import test_connection, validate_source
from app.integrations.runtime.scoring import calculate_health
from app.models.harbor import HarborInstance


class HarborRuntimeAdapter:
    integration_type = 'registry'

    def refresh(self, instance: HarborInstance) -> ValidationResult:
        return validate_source(instance, source_label=instance.name)

    def refresh_health(self, instance: HarborInstance) -> dict[str, Any]:
        return refresh_instance_health(instance)

    def build_client(self, instance: HarborInstance):
        return build_client(instance)

    def execute(self, operation: str, instance: HarborInstance, **kwargs: Any) -> Any:
        if operation == 'connection.test':
            return test_connection(instance)
        if operation == 'client.build':
            return self.build_client(instance)
        if operation == 'runtime.validate':
            return self.refresh(instance)
        if operation == 'runtime.health':
            return self.refresh_health(instance)
        if operation == 'runtime.state':
            return self.get_state(instance, validation_result=kwargs.get('validation_result'))
        raise ValueError(f'Unsupported Harbor integration operation: {operation}')

    def get_state(
        self,
        instance: HarborInstance,
        *,
        validation_result: ValidationResult | Mapping[str, Any] | None = None,
    ) -> RuntimeState:
        now = datetime.now(UTC)
        diagnostics = self._diagnostics(instance, validation_result)
        health = calculate_health(self._factors(instance, diagnostics))
        snapshot = CapabilitySnapshot(
            profile=instance.capability_profile,
            compatibility_profile=instance.compatibility_profile,
            capabilities=tuple(sorted(instance.capabilities or ())),
            observed_at=instance.last_checked_at or instance.last_validated_at or now,
            metadata={
                'version': instance.detected_version,
                'compatibility_status': instance.compatibility_status,
            },
        )
        return RuntimeState(
            integration_type=self.integration_type,
            provider_key=instance.provider_key,
            adapter_key=instance.adapter_key,
            instance_id=str(instance.id),
            instance_name=instance.name,
            observed_at=instance.last_checked_at or instance.last_validated_at or now,
            readiness=instance.readiness_status or 'validation_required',
            health=health,
            diagnostics=diagnostics,
            snapshot=snapshot,
            last_success_at=instance.last_checked_at if instance.last_status == 'connected' else None,
            last_failure_at=instance.last_checked_at if instance.last_status in {'error', 'disconnected'} else None,
            latency_ms=instance.last_response_time_ms,
            message=instance.validation_message or instance.last_error or 'Run Full Validation to establish readiness.',
        )

    @staticmethod
    def _diagnostics(
        instance: HarborInstance,
        result: ValidationResult | Mapping[str, Any] | None,
    ) -> tuple[DiagnosticResult, ...]:
        if isinstance(result, ValidationResult) and result.validation_steps:
            return tuple(
                DiagnosticResult(
                    key=step.key,
                    label=step.label,
                    category='compatibility' if step.key == 'compatibility' else 'api',
                    status=step.status,
                    detail=step.detail,
                    duration_ms=step.response_time_ms,
                    severity='critical' if step.status == 'failed' else 'info',
                    recommendation='Review endpoint, credentials, TLS, and Harbor permissions.'
                    if step.status == 'failed'
                    else None,
                )
                for step in result.validation_steps
            )

        if isinstance(result, Mapping) and result.get('health_status'):
            status = str(result.get('health_status') or 'unknown')
            return (
                DiagnosticResult(
                    key='provider_health',
                    label='Provider Health',
                    category='runtime',
                    status='success' if status == 'healthy' else 'failed',
                    detail=f'Harbor reports overall health: {status}.',
                    duration_ms=int(result.get('response_time_ms') or 0),
                ),
            )

        return (
            DiagnosticResult(
                key='runtime',
                label='Runtime observation',
                category='runtime',
                status='success' if instance.last_status == 'connected' else (
                    'failed' if instance.last_status in {'error', 'disconnected'} else 'unknown'
                ),
                detail=instance.last_error or instance.validation_message or 'Runtime has not been observed.',
            ),
        )

    @staticmethod
    def _factors(
        instance: HarborInstance,
        diagnostics: tuple[DiagnosticResult, ...],
    ) -> tuple[HealthFactor, ...]:
        api_failed = any(row.status == 'failed' and row.category in {'api', 'runtime'} for row in diagnostics)
        api_warning = any(row.status == 'warning' and row.category in {'api', 'runtime'} for row in diagnostics)
        capabilities_ready = bool(instance.capabilities)
        return (
            HealthFactor(
                'connectivity',
                'Connectivity',
                'success' if instance.last_status == 'connected' else (
                    'failed' if instance.last_status in {'error', 'disconnected'} else 'unknown'
                ),
                30,
                100 if instance.last_status == 'connected' else (
                    0 if instance.last_status in {'error', 'disconnected'} else 50
                ),
                instance.last_error or '',
            ),
            HealthFactor(
                'readiness',
                'Readiness',
                'success' if instance.readiness_status == 'ready' else (
                    'failed' if instance.readiness_status == 'blocked' else 'warning'
                ),
                25,
                100 if instance.readiness_status == 'ready' else (
                    0 if instance.readiness_status == 'blocked' else 65
                ),
                instance.validation_message or '',
            ),
            HealthFactor(
                'provider_api',
                'Provider API',
                'failed' if api_failed else (
                    'warning' if api_warning else ('success' if instance.last_status == 'connected' else 'unknown')
                ),
                25,
                0 if api_failed else (65 if api_warning else (100 if instance.last_status == 'connected' else 50)),
            ),
            HealthFactor(
                'capability',
                'Capability discovery',
                'success' if capabilities_ready else 'unknown',
                10,
                100 if capabilities_ready else 50,
            ),
            HealthFactor(
                'latency',
                'Latency',
                'warning' if (instance.last_response_time_ms or 0) > 1500 else (
                    'success' if instance.last_response_time_ms is not None else 'unknown'
                ),
                10,
                60 if (instance.last_response_time_ms or 0) > 1500 else (
                    100 if instance.last_response_time_ms is not None else 50
                ),
            ),
        )


runtime_adapter = HarborRuntimeAdapter()

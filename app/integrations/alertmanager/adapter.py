from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.integrations.alertmanager.binding_management import (
    create_binding,
    update_binding_selector,
)
from app.integrations.alertmanager.binding_validation import validate_binding
from app.integrations.alertmanager.client_factory import build_client
from app.integrations.alertmanager.contracts import ValidationResult
from app.integrations.alertmanager.runtime import refresh_instance_health
from app.integrations.alertmanager.validation import validate_source
from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.runtime.scoring import calculate_health
from app.models.alertmanager import AlertmanagerInstance


class AlertmanagerRuntimeAdapter:
    provider = 'alertmanager'

    def refresh(self, instance: AlertmanagerInstance) -> ValidationResult:
        return validate_source(instance, source_label=instance.name)

    def refresh_health(self, instance: AlertmanagerInstance) -> dict:
        return refresh_instance_health(instance)

    def build_client(self, instance: AlertmanagerInstance):
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
        if operation == 'binding.create':
            return create_binding(
                instance=instance,
                scope_type=str(kwargs.get('scope_type') or ''),
                scope_key=str(kwargs.get('scope_key') or ''),
                role=str(kwargs.get('role') or 'primary'),
                priority=int(kwargs.get('priority', 100)),
                enabled=bool(kwargs.get('enabled', True)),
                selector_label=kwargs.get('selector_label'),
                selector_value=kwargs.get('selector_value'),
                selector_operator=str(kwargs.get('selector_operator') or '='),
                capability_scope=kwargs.get('capability_scope'),
                commit=bool(kwargs.get('commit', True)),
            )
        if operation == 'binding.selector.update':
            binding = kwargs.get('binding')
            if binding is None:
                raise ValueError('Alertmanager binding.selector.update requires a binding.')
            return update_binding_selector(
                instance=instance,
                binding=binding,
                selector_label=kwargs.get('selector_label'),
                selector_value=kwargs.get('selector_value'),
                selector_operator=str(kwargs.get('selector_operator') or '='),
                commit=bool(kwargs.get('commit', True)),
            )
        if operation == 'binding.validate':
            binding = kwargs.get('binding')
            if binding is None:
                raise ValueError('Alertmanager binding.validate requires a binding.')
            return validate_binding(
                instance=instance,
                binding=binding,
                commit=bool(kwargs.get('commit', True)),
            )
        raise ValueError(f'Unsupported Alertmanager integration operation: {operation}')

    def get_state(
        self,
        instance: AlertmanagerInstance,
        *,
        validation_result: ValidationResult | Mapping[str, Any] | None = None,
    ) -> RuntimeState:
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
        failure_at = (
            instance.last_checked_at if instance.last_status in {'error', 'disconnected', 'incompatible'} else None
        )
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
            message=instance.validation_message
            or instance.last_error
            or 'Run runtime validation to observe this source.',
        )

    @staticmethod
    def _validation_steps(
        result: ValidationResult | Mapping[str, Any] | None,
    ) -> tuple[Any, ...]:
        """Return validation steps from either canonical objects or serialized payloads.

        Full validation returns ``ValidationResult`` while lightweight runtime
        health returns a dictionary. Worker boundaries may also serialize the
        canonical result before runtime state construction, so the adapter must
        accept both representations.
        """
        if result is None:
            return ()
        if isinstance(result, Mapping):
            steps = result.get('validation_steps') or ()
            return tuple(step for step in steps if isinstance(step, Mapping))
        return tuple(getattr(result, 'validation_steps', ()) or ())

    @staticmethod
    def _diagnostics(
        instance: AlertmanagerInstance,
        result: ValidationResult | Mapping[str, Any] | None,
    ) -> tuple[DiagnosticResult, ...]:
        steps = AlertmanagerRuntimeAdapter._validation_steps(result)
        if steps:
            diagnostics: list[DiagnosticResult] = []
            for step in steps:
                if isinstance(step, Mapping):
                    key = str(step.get('key') or 'validation')
                    label = str(step.get('label') or 'Validation')
                    step_status = str(step.get('status') or 'unknown')
                    detail = str(step.get('detail') or 'No validation detail was recorded.')
                    response_time_ms = step.get('response_time_ms')
                else:
                    key = str(step.key)
                    label = str(step.label)
                    step_status = str(step.status)
                    detail = str(step.detail)
                    response_time_ms = step.response_time_ms
                diagnostics.append(
                    DiagnosticResult(
                        key=key,
                        label=label,
                        category='api' if key.endswith('_v2') else 'compatibility',
                        status=step_status,
                        detail=detail,
                        duration_ms=response_time_ms,
                        severity='critical' if step_status == 'failed' else 'info',
                        recommendation='Review endpoint, credentials, TLS, and provider logs.'
                        if step_status == 'failed'
                        else None,
                    )
                )
            return tuple(diagnostics)
        status = (
            'success'
            if instance.last_status == 'connected'
            else ('failed' if instance.last_status in {'error', 'disconnected', 'incompatible'} else 'unknown')
        )
        return (
            DiagnosticResult(
                'runtime',
                'Runtime observation',
                'runtime',
                status,
                instance.last_error or instance.validation_message or 'Validation has not been observed.',
            ),
        )

    @staticmethod
    def _factors(instance: AlertmanagerInstance, diagnostics: tuple[DiagnosticResult, ...]) -> tuple[HealthFactor, ...]:
        api_failed = any(row.status == 'failed' and row.category == 'api' for row in diagnostics)
        return (
            HealthFactor(
                'connectivity',
                'Connectivity',
                'failed'
                if instance.last_status in {'error', 'disconnected'}
                else ('success' if instance.last_status == 'connected' else 'unknown'),
                30,
                0
                if instance.last_status in {'error', 'disconnected'}
                else (100 if instance.last_status == 'connected' else 55),
                instance.last_error or '',
            ),
            HealthFactor(
                'readiness',
                'Readiness',
                'failed'
                if instance.readiness_status == 'blocked'
                else ('success' if instance.readiness_status == 'ready' else 'warning'),
                25,
                0 if instance.readiness_status == 'blocked' else (100 if instance.readiness_status == 'ready' else 65),
                instance.validation_message or '',
            ),
            HealthFactor(
                'api',
                'Provider API',
                'failed' if api_failed else ('success' if instance.last_status == 'connected' else 'unknown'),
                25,
                0 if api_failed else (100 if instance.last_status == 'connected' else 55),
            ),
            HealthFactor(
                'capability',
                'Capability discovery',
                'success' if instance.capabilities else 'unknown',
                10,
                100 if instance.capabilities else 50,
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


runtime_adapter = AlertmanagerRuntimeAdapter()

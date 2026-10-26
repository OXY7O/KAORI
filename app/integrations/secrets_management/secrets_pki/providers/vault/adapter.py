from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.compatibility import evaluate_compatibility
from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.runtime.scoring import calculate_health
from app.integrations.secrets_management.secrets_pki.providers.vault.client import VaultClient, VaultProviderError
from app.models.vault import VaultInstance

_CAPABILITY_PROFILE = 'vault.readiness.v1'


def build_client(instance: VaultInstance) -> VaultClient:
    return VaultClient(
        endpoint=instance.endpoint,
        namespace=instance.namespace,
        auth_mount=instance.auth_mount,
        role_id=instance.role_id,
        secret_id=instance.secret_id,
        timeout=instance.timeout,
    )


class VaultRuntimeAdapter:
    integration_type = 'secrets_pki'

    def execute(self, operation: str, instance: VaultInstance, **kwargs: Any) -> Any:
        if operation == 'connection.test':
            return build_client(instance).test_connection()
        if operation == 'client.build':
            return build_client(instance)
        if operation == 'runtime.validate':
            return self.refresh(instance)
        if operation == 'runtime.health':
            return self.refresh_health(instance)
        if operation == 'runtime.state':
            return self.get_state(instance, validation_result=kwargs.get('validation_result'))
        raise ValueError('Unsupported Secrets & PKI integration operation.')

    def refresh(self, instance: VaultInstance) -> dict[str, Any]:
        """Full Validation: AppRole access and qualified API capability, not a provider write."""
        now = datetime.now(UTC)
        try:
            client = build_client(instance)
            evidence = client.validate_capabilities()
            connection = {
                'version': evidence['health']['version'],
                'health_status': evidence['health']['status'],
                'response_time_ms': evidence['response_time_ms'],
            }
            capability = {'mount_metadata': evidence['mount_metadata']}
        except VaultProviderError as exc:
            instance.readiness_status = 'blocked'
            instance.validation_message = str(exc)
            instance.last_validated_at = now
            instance.last_status = 'disconnected'
            instance.last_error = str(exc)
            instance.last_checked_at = now
            db.session.commit()
            return {'connected': False, 'readiness_status': 'blocked', 'reason': str(exc)}
        instance.detected_version = connection['version']
        instance.capabilities = ['health', 'approle', 'token_lookup'] + (
            ['mount_metadata'] if capability['mount_metadata'] == 'available' else []
        )
        compatibility = evaluate_compatibility('vault', connection['version'], instance.capabilities)
        instance.compatibility_status = compatibility.status
        instance.compatibility_profile = compatibility.profile_key
        instance.capability_profile = _CAPABILITY_PROFILE
        instance.validation_summary = {
            'health_status': connection['health_status'],
            'mount_metadata': capability['mount_metadata'],
            'compatibility_status': compatibility.status,
            'support_level': compatibility.support_level,
        }
        instance.validation_message = compatibility.message
        instance.readiness_status = compatibility.readiness
        instance.last_status = 'connected'
        instance.last_error = None
        instance.last_checked_at = now
        instance.last_validated_at = now
        instance.last_response_time_ms = int(connection['response_time_ms'])
        db.session.commit()
        return {
            'connected': True,
            'readiness_status': compatibility.readiness,
            'version': instance.detected_version,
            'compatibility_status': compatibility.status,
            'compatibility_profile': compatibility.profile_key,
            'capabilities': instance.capabilities,
            'capability_profile': _CAPABILITY_PROFILE,
            'reason': instance.validation_message,
        }

    def refresh_health(self, instance: VaultInstance) -> dict[str, Any]:
        try:
            health = build_client(instance).health()
        except VaultProviderError as exc:
            instance.last_status = 'disconnected'
            instance.last_error = str(exc)
            health = {'status': 'unavailable'}
        else:
            instance.last_status = (
                'connected' if health['status'] in {'active', 'standby', 'performance_standby'} else 'disconnected'
            )
            instance.last_error = None
        instance.last_checked_at = datetime.now(UTC)
        instance.validation_summary = {**(instance.validation_summary or {}), 'health_status': health['status']}
        db.session.commit()
        return {'health_status': health['status']}

    def get_state(self, instance: VaultInstance, *, validation_result: Any = None) -> RuntimeState:
        now = datetime.now(UTC)
        health_status = str((instance.validation_summary or {}).get('health_status') or 'unknown')
        ready = instance.readiness_status == 'ready'
        available = health_status in {'active', 'standby', 'performance_standby'}
        unknown = health_status == 'unknown'
        health = calculate_health(
            (
                HealthFactor(
                    'provider_health',
                    'Provider Health',
                    'success' if available else ('unknown' if unknown else 'failed'),
                    50,
                    100 if available else (50 if unknown else 0),
                ),
                HealthFactor(
                    'validation', 'Full Validation', 'success' if ready else 'warning', 50, 100 if ready else 50
                ),
            )
        )
        return RuntimeState(
            integration_type=self.integration_type,
            provider_key='vault',
            adapter_key='vault_http_v1',
            instance_id=str(instance.id),
            instance_name=instance.name,
            observed_at=instance.last_checked_at or instance.last_validated_at or now,
            readiness=instance.readiness_status or 'validation_required',
            health=health,
            diagnostics=(
                DiagnosticResult(
                    key='vault_health',
                    label='Vault Health',
                    category='runtime',
                    status='success' if available else ('unknown' if health_status == 'unknown' else 'failed'),
                    detail=f'Vault node state: {health_status}.',
                ),
            ),
            snapshot=CapabilitySnapshot(
                profile=instance.capability_profile,
                compatibility_profile=instance.compatibility_profile,
                capabilities=tuple(instance.capabilities or ()),
                observed_at=instance.last_validated_at or now,
                metadata={
                    'version': instance.detected_version,
                    'vault_state': health_status,
                    'compatibility_status': instance.compatibility_status,
                },
            ),
            last_success_at=instance.last_checked_at if available else None,
            last_failure_at=instance.last_checked_at if not available else None,
            latency_ms=instance.last_response_time_ms,
            message=instance.validation_message or instance.last_error or 'Run Full Validation.',
        )


runtime_adapter = VaultRuntimeAdapter()

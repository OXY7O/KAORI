"""Read-only Ansible provider adapter: no embedded Runner or SSH execution."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthState, RuntimeState
from app.integrations.contracts.exceptions import IntegrationOperationNotSupported
from app.models.integration import IntegrationInstance


class AnsibleRuntimeAdapter:
    integration_type = 'infrastructure_automation'

    def refresh(self, instance: IntegrationInstance) -> None:
        raise IntegrationOperationNotSupported(
            'Remote Ansible provider validation requires approved host trust and credential authority.'
        )

    def execute(self, operation: str, instance: IntegrationInstance, **kwargs: Any) -> Any:
        if operation == 'runtime.state':
            return self.get_state(instance)
        if operation == 'host_facts.collect':
            from app.integrations.orchestration.infrastructure_automation.providers.ansible.application.service import (
                enqueue_read_only_pilot,
            )

            return enqueue_read_only_pilot(instance, requested_by_user_id=kwargs.get('requested_by_user_id'))
        raise IntegrationOperationNotSupported(f'Unsupported Ansible operation: {operation}')

    def get_state(self, instance: IntegrationInstance, *, validation_result: Any | None = None) -> RuntimeState:
        _ = validation_result
        now = datetime.now(UTC)
        # A successful localhost job does not validate an external Linux host or production EE.
        blocked = not instance.enabled or instance.lifecycle_status != 'active'
        return RuntimeState(
            integration_type=self.integration_type,
            provider_key='ansible',
            adapter_key='ansible_runner',
            instance_id=str(instance.id),
            instance_name=instance.name,
            observed_at=instance.last_checked_at or now,
            readiness='blocked' if blocked else 'validation_required',
            health=HealthState(
                status='unhealthy' if blocked else 'degraded',
                score=0,
                summary='External host identity, SSH host-key trust and execution EE are not verified.',
            ),
            diagnostics=(
                DiagnosticResult(
                    key='remote_target',
                    label='Remote host authorization',
                    category='security',
                    status='unknown',
                    detail='Only isolated worker localhost facts may be requested in non-production.',
                    recommendation='Complete trusted inventory and credential authority before remote UAT.',
                ),
            ),
            snapshot=CapabilitySnapshot(
                profile='ansible-localhost-pilot-v1',
                compatibility_profile='ansible-localhost-pilot-v1',
                capabilities=(),
                observed_at=instance.last_checked_at or now,
                metadata={'source': 'pinned_git', 'target': 'automation-worker:localhost'},
            ),
            message='Worker localhost pilot only. External provider readiness is not verified.',
        )


runtime_adapter = AnsibleRuntimeAdapter()

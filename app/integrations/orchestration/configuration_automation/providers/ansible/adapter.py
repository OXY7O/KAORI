"""Inert Ansible provider descriptor; no arbitrary runner dispatch via Kernel."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.contracts import CapabilitySnapshot, HealthState, RuntimeState
from app.integrations.contracts.exceptions import IntegrationOperationNotSupported
from app.integrations.orchestration.configuration_automation.providers.ansible.service import (
    AnsibleConnectionRecord,
    source_validation_posture,
)


class AnsibleSourceAdapter:
    integration_type = 'configuration_automation'

    def refresh(self, instance: AnsibleConnectionRecord) -> RuntimeState:
        return self.get_state(instance)

    def get_state(self, instance: AnsibleConnectionRecord, *, validation_result: Any | None = None) -> RuntimeState:
        canonical = instance.integration_instance
        posture = source_validation_posture(canonical)
        observed_at = canonical.created_at or datetime.now(UTC)
        return RuntimeState(
            integration_type=self.integration_type,
            provider_key='ansible',
            adapter_key='ansible_runner',
            instance_id=str(canonical.id),
            instance_name=canonical.name,
            observed_at=observed_at,
            readiness='validation_required',
            health=HealthState(status='not_observed', score=0, summary='Real host/worker runtime not observed.'),
            diagnostics=(),
            snapshot=CapabilitySnapshot(
                profile=str((canonical.metadata_json or {}).get('profile_key') or ''),
                compatibility_profile=None,
                capabilities=(),
                observed_at=observed_at,
                metadata={'source_status': posture['source_state']},
            ),
            message=f'{posture["source_label"]}. Remote operation and infrastructure readiness are not admitted.',
        )

    def execute(self, operation: str, instance: AnsibleConnectionRecord, **kwargs: Any) -> Any:
        raise IntegrationOperationNotSupported('Ansible execution operations require separate provider admission.')


runtime_adapter = AnsibleSourceAdapter()

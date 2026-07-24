from __future__ import annotations

from typing import Any

from app.integrations.contracts import RuntimeAdapter, RuntimeState
from app.integrations.runtime.repository import persist_runtime_state
from app.models.runtime import IntegrationRuntimeObservation


def refresh_runtime(adapter: RuntimeAdapter, instance: Any) -> tuple[Any, RuntimeState]:
    result = adapter.refresh(instance)
    return result, adapter.get_state(instance, validation_result=result)


def get_runtime_state(adapter: RuntimeAdapter, instance: Any) -> RuntimeState:
    return adapter.get_state(instance)


def _canonical_instance_id(instance: Any) -> int | None:
    value = getattr(instance, 'integration_instance_id', None)
    if isinstance(value, int):
        return value

    connection = getattr(instance, 'kubernetes_connection', None)
    value = getattr(connection, 'integration_instance_id', None)
    return value if isinstance(value, int) else None


def refresh_and_record(
    adapter: RuntimeAdapter,
    instance: Any,
    *,
    trigger_type: str = 'manual',
) -> tuple[Any, RuntimeState, IntegrationRuntimeObservation]:
    """Refresh one provider and persist its canonical runtime observation."""
    validation_result, state = refresh_runtime(adapter, instance)
    observation = persist_runtime_state(
        state,
        trigger_type=trigger_type,
        integration_instance_id=_canonical_instance_id(instance),
    )
    return validation_result, state, observation

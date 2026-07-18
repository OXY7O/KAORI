from __future__ import annotations

from typing import Any

from .refresh import refresh_runtime
from .repository import persist_runtime_state


def _canonical_instance_id(instance: Any) -> int | None:
    value = getattr(instance, 'integration_instance_id', None)
    if value is not None:
        return int(value)
    connection = getattr(instance, 'kubernetes_connection', None)
    value = getattr(connection, 'integration_instance_id', None)
    return int(value) if value is not None else None


def refresh_and_record(adapter: Any, instance: Any, *, trigger_type: str = 'manual'):
    validation_result, state = refresh_runtime(adapter, instance)
    observation = persist_runtime_state(
        state,
        trigger_type=trigger_type,
        integration_instance_id=_canonical_instance_id(instance),
    )
    return validation_result, state, observation

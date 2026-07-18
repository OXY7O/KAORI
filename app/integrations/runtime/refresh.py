from __future__ import annotations

from typing import Any

from app.integrations.runtime.contracts import RuntimeAdapter, RuntimeState


def refresh_runtime(adapter: RuntimeAdapter, instance: Any) -> tuple[Any, RuntimeState]:
    result = adapter.refresh(instance)
    return result, adapter.get_state(instance, validation_result=result)


def get_runtime_state(adapter: RuntimeAdapter, instance: Any) -> RuntimeState:
    return adapter.get_state(instance)

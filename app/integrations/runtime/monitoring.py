from __future__ import annotations
from typing import Any
from .refresh import refresh_runtime
from .repository import persist_runtime_state

def refresh_and_record(adapter: Any, instance: Any, *, trigger_type: str = 'manual'):
    validation_result, state = refresh_runtime(adapter, instance)
    observation = persist_runtime_state(state, trigger_type=trigger_type)
    return validation_result, state, observation

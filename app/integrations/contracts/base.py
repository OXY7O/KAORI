from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.integrations.contracts.results import RuntimeState


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Minimum contract implemented by every KAORI integration adapter."""

    provider: str

    def refresh(self, instance: Any) -> Any:
        """Rebuild compatibility and capability evidence for one instance."""

    def get_state(self, instance: Any, *, validation_result: Any | None = None) -> RuntimeState:
        """Translate persisted or fresh provider data into shared runtime state."""


@runtime_checkable
class OperationAdapter(RuntimeAdapter, Protocol):
    def execute(self, operation: str, instance: Any, **kwargs: Any) -> Any:
        """Execute one provider-owned operation through a stable operation key."""

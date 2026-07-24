from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from threading import RLock
from typing import Any

from app.extensions.db import db
from app.integrations.contracts import (
    IntegrationInstanceNotFound,
    IntegrationNotRegistered,
    IntegrationOperationNotSupported,
    OperationAdapter,
)

InstanceLoader = Callable[[int], Any | None]


@dataclass(frozen=True, slots=True)
class IntegrationModule:
    """One independently maintainable integration registered with KAORI core."""

    provider_type: str
    label: str
    adapter: OperationAdapter
    instance_loader: InstanceLoader
    module_path: str
    worker_queue: str
    worker_domain: str
    operations: frozenset[str]
    operation_queues: Mapping[str, str]
    capability_keys: tuple[str, ...] = ()
    compatibility_profiles: tuple[str, ...] = ()

    def queue_for(self, operation: str) -> str:
        if operation not in self.operations:
            raise IntegrationOperationNotSupported(
                f'{self.label} does not implement integration operation {operation!r}.'
            )
        return str(self.operation_queues.get(operation) or self.worker_queue)

    def get_instance(self, instance_id: int) -> Any:
        instance = self.instance_loader(int(instance_id))
        if instance is None:
            raise IntegrationInstanceNotFound(f'{self.label} instance {instance_id} no longer exists.')
        return instance

    def execute(self, operation: str, instance: Any, **kwargs: Any) -> Any:
        if operation not in self.operations:
            raise IntegrationOperationNotSupported(
                f'{self.label} does not implement integration operation {operation!r}.'
            )
        return self.adapter.execute(operation, instance, **kwargs)


class IntegrationRegistry:
    """Thread-safe registry used by routes, services, workers, and KAORI core."""

    def __init__(self) -> None:
        self._modules: dict[str, IntegrationModule] = {}
        self._lock = RLock()
        self._builtins_loaded = False

    def register(self, module: IntegrationModule, *, replace: bool = False) -> None:
        provider_type = module.provider_type.strip().lower()
        if not provider_type:
            raise ValueError('Integration provider_type is required.')
        if module.adapter.provider != provider_type:
            raise ValueError(
                f'Adapter provider {module.adapter.provider!r} does not match registry key {provider_type!r}.'
            )
        missing_queues = sorted(
            operation for operation in module.operations if not module.operation_queues.get(operation)
        )
        if missing_queues:
            raise ValueError(
                f'Integration provider {provider_type!r} has no worker queue mapping for: {", ".join(missing_queues)}.'
            )
        with self._lock:
            if provider_type in self._modules and not replace:
                raise ValueError(f'Integration provider {provider_type!r} is already registered.')
            self._modules[provider_type] = module

    def _load_builtins(self) -> None:
        with self._lock:
            if self._builtins_loaded:
                return
            for module_path in (
                'app.integrations.kubernetes',
                'app.integrations.prometheus',
                'app.integrations.alertmanager',
            ):
                import_module(module_path)
            self._builtins_loaded = True

    def get(self, provider_type: str) -> IntegrationModule:
        self._load_builtins()
        key = str(provider_type or '').strip().lower()
        module = self._modules.get(key)
        if module is None:
            raise IntegrationNotRegistered(f'Integration provider {key!r} is not registered.')
        return module

    def all(self) -> tuple[IntegrationModule, ...]:
        self._load_builtins()
        return tuple(self._modules[key] for key in sorted(self._modules))

    def execute(
        self,
        provider_type: str,
        operation: str,
        *,
        instance: Any | None = None,
        instance_id: int | None = None,
        **kwargs: Any,
    ) -> Any:
        module = self.get(provider_type)
        selected = instance
        if selected is None:
            if instance_id is None:
                raise ValueError('instance or instance_id is required.')
            selected = module.get_instance(instance_id)
        return module.execute(operation, selected, **kwargs)


registry = IntegrationRegistry()


def model_loader(model: type[Any]) -> InstanceLoader:
    """Build a SQLAlchemy instance loader without leaking ORM access to callers."""

    def load(instance_id: int) -> Any | None:
        return db.session.get(model, int(instance_id))

    return load


def get_integration(provider_type: str) -> IntegrationModule:
    return registry.get(provider_type)


def execute_integration_operation(
    provider_type: str,
    operation: str,
    *,
    instance: Any | None = None,
    instance_id: int | None = None,
    **kwargs: Any,
) -> Any:
    return registry.execute(
        provider_type,
        operation,
        instance=instance,
        instance_id=instance_id,
        **kwargs,
    )

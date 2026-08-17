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
from app.integrations.provider_matrix import provider_kind
from app.integrations.taxonomy import (
    IntegrationCapabilityDefinition,
    IntegrationDomainDefinition,
    get_capability_definition,
    get_domain_definition,
)

InstanceLoader = Callable[[int], Any | None]
CanonicalRecordLoader = Callable[[int], Any | None]
DetailUrlBuilder = Callable[[Any, str], str]
FailureRecorder = Callable[[Any, Exception], None]
RuntimeOverviewBuilder = Callable[[Mapping[tuple[str, str], Any], int | None], list[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class IntegrationImplementation:
    """One product/provider implementation of an integration-type contract.

    Core orchestration resolves this record from the canonical
    ``IntegrationInstance.integration_type`` + ``provider_key`` identity. Product
    models, URLs, failure persistence, and protocol adapters stay behind this
    boundary so adding another provider never adds product conditionals to core.
    """

    integration_type: str
    provider_key: str
    adapter_key: str
    adapter: OperationAdapter
    instance_loader: InstanceLoader
    canonical_record_loader: CanonicalRecordLoader
    module_path: str
    detail_url_builder: DetailUrlBuilder | None = None
    failure_recorder: FailureRecorder | None = None
    runtime_overview_builder: RuntimeOverviewBuilder | None = None

    def get_record(self, record_id: int) -> Any:
        record = self.instance_loader(int(record_id))
        if record is None:
            raise IntegrationInstanceNotFound(
                f'{self.integration_type}:{self.provider_key} record {record_id} no longer exists.'
            )
        return record

    def get_record_for_canonical(self, integration_instance_id: int) -> Any | None:
        return self.canonical_record_loader(int(integration_instance_id))

    def detail_url_for_record(self, record: Any, *, section: str) -> str:
        if self.detail_url_builder is None:
            return '/integrations/'
        return self.detail_url_builder(record, section)

    def record_failure(self, record: Any, error: Exception) -> None:
        if self.failure_recorder is not None:
            self.failure_recorder(record, error)


@dataclass(frozen=True, slots=True)
class IntegrationModule:
    """Provider-neutral integration-type contract registered with KAORI core."""

    integration_type: str
    label: str
    domain_key: str
    capability_key: str
    icon: str
    description: str
    workspace_endpoint: str
    module_path: str
    worker_queue: str
    worker_domain: str
    operations: frozenset[str]
    operation_queues: Mapping[str, str]
    capability_keys: tuple[str, ...] = ()
    compatibility_profiles: tuple[str, ...] = ()
    runtime_label: str | None = None
    navigation_endpoint_prefixes: tuple[str, ...] = ()

    @property
    def domain(self) -> IntegrationDomainDefinition:
        return get_domain_definition(self.domain_key)

    @property
    def capability(self) -> IntegrationCapabilityDefinition:
        return get_capability_definition(self.domain_key, self.capability_key)

    def queue_for(self, operation: str) -> str:
        if operation not in self.operations:
            raise IntegrationOperationNotSupported(
                f'{self.label} does not implement integration operation {operation!r}.'
            )
        return str(self.operation_queues.get(operation) or self.worker_queue)

    def implementation(self, provider_key: str) -> IntegrationImplementation:
        return registry.get_implementation(self.integration_type, provider_key)

    def implementation_for_record(self, record: Any) -> IntegrationImplementation:
        canonical = getattr(record, 'integration_instance', None)
        if canonical is None:
            raise IntegrationInstanceNotFound('Provider record has no canonical integration identity.')
        return self.implementation(str(canonical.provider_key))

    def implementation_for_canonical(self, integration_instance_id: int) -> IntegrationImplementation:
        from app.models.integration import IntegrationInstance

        canonical = db.session.get(IntegrationInstance, int(integration_instance_id))
        if canonical is None or canonical.integration_type != self.integration_type:
            raise IntegrationInstanceNotFound(
                f'{self.label} canonical integration {integration_instance_id} no longer exists.'
            )
        return self.implementation(str(canonical.provider_key))

    def get_record_for_canonical(self, integration_instance_id: int) -> Any | None:
        implementation = self.implementation_for_canonical(integration_instance_id)
        return implementation.get_record_for_canonical(integration_instance_id)

    def require_record_for_canonical(self, integration_instance_id: int) -> Any:
        record = self.get_record_for_canonical(integration_instance_id)
        if record is None:
            raise IntegrationInstanceNotFound(
                f'{self.label} canonical integration {integration_instance_id} has no implementation record.'
            )
        return record

    def detail_url_for_record(self, record: Any, *, section: str) -> str:
        return self.implementation_for_record(record).detail_url_for_record(record, section=section)

    def detail_url(self, integration_instance_id: int, *, section: str) -> str:
        record = self.require_record_for_canonical(integration_instance_id)
        return self.detail_url_for_record(record, section=section)

    def record_failure(self, record: Any, error: Exception) -> None:
        self.implementation_for_record(record).record_failure(record, error)

    def runtime_state(self, record: Any, *, validation_result: Any | None = None):
        implementation = self.implementation_for_record(record)
        return implementation.adapter.get_state(record, validation_result=validation_result)

    def execute(self, operation: str, record: Any, **kwargs: Any) -> Any:
        if operation not in self.operations:
            raise IntegrationOperationNotSupported(
                f'{self.label} does not implement integration operation {operation!r}.'
            )
        implementation = self.implementation_for_record(record)
        return implementation.adapter.execute(operation, record, **kwargs)

    def build_runtime_overview_rows(
        self,
        latest: Mapping[tuple[str, str], Any],
        canonical_id: int | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if canonical_id is not None:
            implementation = self.implementation_for_canonical(canonical_id)
            if implementation.runtime_overview_builder is None:
                return []
            return implementation.runtime_overview_builder(latest, canonical_id)
        for implementation in registry.implementations_for_type(self.integration_type):
            if implementation.runtime_overview_builder is not None:
                rows.extend(implementation.runtime_overview_builder(latest, None))
        return rows


class IntegrationRegistry:
    """Thread-safe integration-type and provider-implementation registry."""

    def __init__(self) -> None:
        self._modules: dict[str, IntegrationModule] = {}
        self._implementations: dict[tuple[str, str], IntegrationImplementation] = {}
        self._lock = RLock()
        self._builtins_loaded = False

    def register(self, module: IntegrationModule, *, replace: bool = False) -> None:
        integration_type = module.integration_type.strip().lower()
        if not integration_type:
            raise ValueError('Integration integration_type is required.')
        get_domain_definition(module.domain_key)
        get_capability_definition(module.domain_key, module.capability_key)
        missing_queues = sorted(
            operation for operation in module.operations if not module.operation_queues.get(operation)
        )
        if missing_queues:
            raise ValueError(
                f'Integration type {integration_type!r} has no worker queue mapping for: {", ".join(missing_queues)}.'
            )
        with self._lock:
            if integration_type in self._modules and not replace:
                raise ValueError(f'Integration type {integration_type!r} is already registered.')
            self._modules[integration_type] = module

    def register_implementation(
        self,
        implementation: IntegrationImplementation,
        *,
        replace: bool = False,
    ) -> None:
        integration_type = implementation.integration_type.strip().lower()
        provider_key = implementation.provider_key.strip().lower()
        adapter_key = implementation.adapter_key.strip().lower()
        definition = provider_kind(integration_type, provider_key)
        if definition.adapter_key != adapter_key:
            raise ValueError(
                f'Provider matrix adapter {definition.adapter_key!r} for {integration_type}:{provider_key} '
                f'does not match implementation adapter {adapter_key!r}.'
            )
        if implementation.adapter.integration_type != integration_type:
            raise ValueError(
                f'Adapter integration type {implementation.adapter.integration_type!r} does not match '
                f'implementation type {integration_type!r}.'
            )
        key = (integration_type, provider_key)
        with self._lock:
            if key in self._implementations and not replace:
                raise ValueError(f'Integration implementation {integration_type}:{provider_key} is already registered.')
            self._implementations[key] = implementation

    def _load_builtins(self) -> None:
        with self._lock:
            if self._builtins_loaded:
                return
            for module_path in (
                'app.integrations.kubernetes',
                'app.integrations.metrics',
                'app.integrations.alertmanager',
                'app.integrations.minio',
            ):
                import_module(module_path)
            self._builtins_loaded = True

    def get(self, integration_type: str) -> IntegrationModule:
        self._load_builtins()
        key = str(integration_type or '').strip().lower()
        module = self._modules.get(key)
        if module is None:
            raise IntegrationNotRegistered(f'Integration type {key!r} is not registered.')
        return module

    def get_implementation(self, integration_type: str, provider_key: str) -> IntegrationImplementation:
        self._load_builtins()
        key = (str(integration_type or '').strip().lower(), str(provider_key or '').strip().lower())
        implementation = self._implementations.get(key)
        if implementation is None:
            raise IntegrationNotRegistered(f'Integration provider implementation {key[0]}:{key[1]} is not registered.')
        return implementation

    def implementations_for_type(self, integration_type: str) -> tuple[IntegrationImplementation, ...]:
        self._load_builtins()
        normalized = str(integration_type or '').strip().lower()
        return tuple(
            implementation
            for (type_key, _), implementation in sorted(self._implementations.items())
            if type_key == normalized
        )

    def all(self) -> tuple[IntegrationModule, ...]:
        self._load_builtins()
        return tuple(
            sorted(
                self._modules.values(),
                key=lambda module: (
                    module.domain.order,
                    module.capability.order,
                    module.label.casefold(),
                    module.integration_type,
                ),
            )
        )

    def execute(
        self,
        integration_type: str,
        operation: str,
        *,
        record: Any | None = None,
        integration_instance_id: int | None = None,
        **kwargs: Any,
    ) -> Any:
        module = self.get(integration_type)
        selected = record
        if selected is None:
            if integration_instance_id is None:
                raise ValueError('record or integration_instance_id is required.')
            selected = module.require_record_for_canonical(integration_instance_id)
        return module.execute(operation, selected, **kwargs)


registry = IntegrationRegistry()


def model_loader(model: type[Any]) -> InstanceLoader:
    """Build a provider implementation record loader."""

    def load(record_id: int) -> Any | None:
        return db.session.get(model, int(record_id))

    return load


def canonical_model_loader(model: type[Any]) -> CanonicalRecordLoader:
    """Build a loader from canonical IntegrationInstance id to implementation record."""

    def load(integration_instance_id: int) -> Any | None:
        return model.query.filter_by(integration_instance_id=int(integration_instance_id)).first()

    return load


def get_integration(integration_type: str) -> IntegrationModule:
    return registry.get(integration_type)


def get_integration_implementation(integration_type: str, provider_key: str) -> IntegrationImplementation:
    return registry.get_implementation(integration_type, provider_key)


def execute_integration_operation(
    integration_type: str,
    operation: str,
    *,
    record: Any | None = None,
    integration_instance_id: int | None = None,
    **kwargs: Any,
) -> Any:
    return registry.execute(
        integration_type,
        operation,
        record=record,
        integration_instance_id=integration_instance_id,
        **kwargs,
    )

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, cast

from app.models.job import JobExecution, JobPolicy


@dataclass(frozen=True, slots=True)
class RegisteredJobDispatchResult:
    """Outcome returned by one registered job dispatcher."""

    status: str
    message: str
    job: JobExecution | None = None
    created: bool = False

    @property
    def accepted(self) -> bool:
        return self.job is not None


class JobDispatcher(Protocol):
    def __call__(
        self,
        *,
        requested_by_user_id: int | None,
        trigger_type: str,
        parameters: dict[str, Any] | None = None,
    ) -> RegisteredJobDispatchResult: ...


class JobContextBuilder(Protocol):
    def __call__(self, policy: JobPolicy) -> dict[str, Any]: ...


def _resolve_callable(path: str) -> object:
    module_name, separator, attribute_name = path.partition(':')
    if not separator or not module_name or not attribute_name:
        raise ValueError(f'Invalid registered job callable path: {path}')
    module = import_module(module_name)
    try:
        return getattr(module, attribute_name)
    except AttributeError as exc:
        raise LookupError(f'Registered job callable not found: {path}') from exc


@dataclass(frozen=True, slots=True)
class JobDefinition:
    """Static catalog entry describing one configurable KAORI background job."""

    key: str
    name: str
    domain: str
    description: str
    icon: str
    queue_name: str
    workload_class: str
    job_type: str
    operation: str
    scope_type: str
    scope_key: str
    configure_permission: str
    execute_permission: str
    domain_execute_permission: str | None
    dispatcher_path: str
    context_builder_path: str
    configuration_template: str
    default_enabled: bool = True
    default_interval_minutes: int = 60
    minimum_interval_minutes: int = 5
    maximum_interval_minutes: int = 1440
    schedule_supported: bool = True
    manual_execution_supported: bool = True
    safety_summary: str = ''
    execution_summary: str = 'Run the job manually or wait for the saved automatic policy.'
    recent_execution_summary: str = 'Latest scheduled and manual executions for this job.'
    default_configuration: dict[str, Any] | None = None

    def dispatch(
        self,
        *,
        requested_by_user_id: int | None,
        trigger_type: str,
        parameters: dict[str, Any] | None = None,
    ) -> RegisteredJobDispatchResult:
        dispatcher = cast(JobDispatcher, _resolve_callable(self.dispatcher_path))
        return dispatcher(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
            parameters=parameters,
        )

    def build_context(self, policy: JobPolicy) -> dict[str, Any]:
        builder = cast(JobContextBuilder, _resolve_callable(self.context_builder_path))
        return builder(policy)

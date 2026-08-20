from __future__ import annotations

from app.platform_operations.jobs.definition_catalog import load_job_definitions
from app.platform_operations.jobs.definition_types import JobDefinition

_JOB_DEFINITIONS: tuple[JobDefinition, ...] = load_job_definitions()
_JOB_DEFINITION_BY_KEY = {definition.key: definition for definition in _JOB_DEFINITIONS}
_JOB_DEFINITION_BY_OPERATION = {definition.operation: definition for definition in _JOB_DEFINITIONS}


def refresh_job_registry() -> tuple[JobDefinition, ...]:
    """Reload the declarative job catalog for long-lived web/worker processes.

    KAORI development and rolling deployments can replace the source-controlled
    YAML catalog while an existing Flask or Celery process is still alive. The
    registry therefore refreshes at dispatch boundaries instead of requiring a
    process restart just to discover a newly registered job definition.
    """
    global _JOB_DEFINITIONS, _JOB_DEFINITION_BY_KEY, _JOB_DEFINITION_BY_OPERATION

    definitions = load_job_definitions()
    _JOB_DEFINITIONS = definitions
    _JOB_DEFINITION_BY_KEY = {definition.key: definition for definition in definitions}
    _JOB_DEFINITION_BY_OPERATION = {definition.operation: definition for definition in definitions}
    return definitions


def list_job_definitions() -> tuple[JobDefinition, ...]:
    # Configuration and scheduler surfaces must reflect the source-controlled
    # catalog even when the serving process predates a newly added definition.
    return refresh_job_registry()


def get_job_definition(job_key: str) -> JobDefinition:
    definition = _JOB_DEFINITION_BY_KEY.get(job_key)
    if definition is None:
        # Self-heal a long-lived process that imported the registry before the
        # requested job was added to registered_jobs.yaml.
        refresh_job_registry()
        definition = _JOB_DEFINITION_BY_KEY.get(job_key)
    if definition is None:
        raise LookupError(f'Unknown registered job: {job_key}')
    return definition


def get_job_definition_by_operation(operation: str) -> JobDefinition:
    definition = _JOB_DEFINITION_BY_OPERATION.get(operation)
    if definition is None:
        refresh_job_registry()
        definition = _JOB_DEFINITION_BY_OPERATION.get(operation)
    if definition is None:
        raise LookupError(f'Unknown registered job operation: {operation}')
    return definition

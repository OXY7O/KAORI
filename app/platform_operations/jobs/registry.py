from __future__ import annotations

from app.platform_operations.jobs.definition_catalog import load_job_definitions
from app.platform_operations.jobs.definition_types import JobDefinition

_JOB_DEFINITIONS: tuple[JobDefinition, ...] = load_job_definitions()
_JOB_DEFINITION_BY_KEY = {definition.key: definition for definition in _JOB_DEFINITIONS}
_JOB_DEFINITION_BY_OPERATION = {definition.operation: definition for definition in _JOB_DEFINITIONS}


def list_job_definitions() -> tuple[JobDefinition, ...]:
    return _JOB_DEFINITIONS


def get_job_definition(job_key: str) -> JobDefinition:
    try:
        return _JOB_DEFINITION_BY_KEY[job_key]
    except KeyError as exc:
        raise LookupError(f'Unknown registered job: {job_key}') from exc


def get_job_definition_by_operation(operation: str) -> JobDefinition:
    try:
        return _JOB_DEFINITION_BY_OPERATION[operation]
    except KeyError as exc:
        raise LookupError(f'Unknown registered job operation: {operation}') from exc

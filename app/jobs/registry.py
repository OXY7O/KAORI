from __future__ import annotations

from app.jobs.definitions import (
    ANALYTICS_REFRESH_DEFINITION,
    FORECAST_REFRESH_DEFINITION,
    INVENTORY_SYNC_DEFINITION,
    REPORT_SCHEDULE_DEFINITION,
    TLS_CERTIFICATE_SYNC_DEFINITION,
    JobDefinition,
)

_JOB_DEFINITIONS: tuple[JobDefinition, ...] = (
    INVENTORY_SYNC_DEFINITION,
    REPORT_SCHEDULE_DEFINITION,
    TLS_CERTIFICATE_SYNC_DEFINITION,
    ANALYTICS_REFRESH_DEFINITION,
    FORECAST_REFRESH_DEFINITION,
)
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


def job_operation_label(operation: str) -> str:
    """Return the canonical user-facing name for a registered job operation."""
    try:
        return get_job_definition_by_operation(operation).name
    except LookupError:
        return operation.replace('_', ' ').title()

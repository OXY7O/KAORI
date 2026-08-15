from __future__ import annotations

from typing import Any

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import (
    optional_str,
    require_bool,
    require_int,
    require_list,
    require_mapping,
    require_str,
    unique_by,
)
from app.jobs.definition_types import JobDefinition


def _raw_jobs() -> list[dict[str, Any]]:
    document = load_definition_document('jobs/registered_jobs.yaml', expected_kind='registered_jobs')
    raw = [
        dict(require_mapping(item, f'jobs[{index}]'))
        for index, item in enumerate(require_list(document.get('jobs'), 'jobs'))
    ]
    unique_by(raw, 'key', 'jobs')
    unique_by(raw, 'operation', 'jobs')
    return raw


def operation_labels() -> dict[str, str]:
    return {
        require_str(item, 'operation', f'jobs[{index}]'): require_str(item, 'name', f'jobs[{index}]')
        for index, item in enumerate(_raw_jobs())
    }


def load_job_definitions() -> tuple[JobDefinition, ...]:
    output: list[JobDefinition] = []
    for index, raw in enumerate(_raw_jobs()):
        path = f'jobs[{index}]'
        configuration = raw.get('default_configuration')
        if configuration is not None:
            configuration = dict(require_mapping(configuration, f'{path}.default_configuration'))
        output.append(JobDefinition(
            key=require_str(raw, 'key', path),
            name=require_str(raw, 'name', path),
            domain=require_str(raw, 'domain', path),
            description=require_str(raw, 'description', path),
            icon=require_str(raw, 'icon', path),
            queue_name=require_str(raw, 'queue_name', path),
            workload_class=require_str(raw, 'workload_class', path),
            job_type=require_str(raw, 'job_type', path),
            operation=require_str(raw, 'operation', path),
            scope_type=require_str(raw, 'scope_type', path),
            scope_key=require_str(raw, 'scope_key', path),
            configure_permission=require_str(raw, 'configure_permission', path),
            execute_permission=require_str(raw, 'execute_permission', path),
            domain_execute_permission=optional_str(raw, 'domain_execute_permission', path),
            dispatcher_path=require_str(raw, 'dispatcher_path', path),
            context_builder_path=require_str(raw, 'context_builder_path', path),
            configuration_template=require_str(raw, 'configuration_template', path),
            default_enabled=require_bool(raw, 'default_enabled', path, default=True),
            default_interval_minutes=require_int(raw, 'default_interval_minutes', path, default=60),
            minimum_interval_minutes=require_int(raw, 'minimum_interval_minutes', path, default=5),
            maximum_interval_minutes=require_int(raw, 'maximum_interval_minutes', path, default=1440),
            schedule_supported=require_bool(raw, 'schedule_supported', path, default=True),
            manual_execution_supported=require_bool(raw, 'manual_execution_supported', path, default=True),
            safety_summary=str(raw.get('safety_summary') or ''),
            execution_summary=str(
                raw.get('execution_summary')
                or 'Run the job manually or wait for the saved automatic policy.'
            ),
            recent_execution_summary=str(
                raw.get('recent_execution_summary')
                or 'Latest scheduled and manual executions for this job.'
            ),
            default_configuration=configuration,
        ))
    return tuple(output)

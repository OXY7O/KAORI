from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.extensions.db import db
from app.models.job import JobPolicy
from app.platform_operations.jobs.definitions.base import JobDefinition
from app.platform_operations.jobs.registry import get_job_definition, list_job_definitions


def utcnow() -> datetime:
    return datetime.now(UTC)


def calculate_next_run(*, interval_minutes: int, now: datetime | None = None) -> datetime:
    return (now or utcnow()) + timedelta(minutes=interval_minutes)


def _new_policy(definition: JobDefinition) -> JobPolicy:
    policy = JobPolicy()
    policy.job_key = definition.key
    policy.enabled = definition.default_enabled
    policy.trigger_type = 'interval'
    policy.interval_minutes = definition.default_interval_minutes
    policy.timezone = 'UTC'
    policy.scope_type = definition.scope_type
    policy.scope_key = definition.scope_key
    policy.configuration_json = dict(definition.default_configuration or {})
    policy.next_run_at = (
        calculate_next_run(interval_minutes=definition.default_interval_minutes)
        if definition.default_enabled and definition.schedule_supported
        else None
    )
    return policy


def get_or_create_job_policy(job_key: str) -> JobPolicy:
    definition = get_job_definition(job_key)
    policy = JobPolicy.query.filter_by(
        job_key=definition.key,
        scope_type=definition.scope_type,
        scope_key=definition.scope_key,
    ).first()
    if policy is not None:
        return policy

    policy = _new_policy(definition)
    db.session.add(policy)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        policy = JobPolicy.query.filter_by(
            job_key=definition.key,
            scope_type=definition.scope_type,
            scope_key=definition.scope_key,
        ).one()
    return policy


def ensure_registered_job_policies() -> list[JobPolicy]:
    return [get_or_create_job_policy(definition.key) for definition in list_job_definitions()]


def update_job_policy(
    *,
    job_key: str,
    enabled: bool,
    interval_minutes: int,
    user_id: int,
    configuration: dict[str, object] | None = None,
) -> JobPolicy:
    definition = get_job_definition(job_key)
    if not definition.schedule_supported:
        raise ValueError(f'{definition.name} does not support automatic scheduling.')
    if not definition.minimum_interval_minutes <= interval_minutes <= definition.maximum_interval_minutes:
        raise ValueError(
            f'{definition.name} interval must be between '
            f'{definition.minimum_interval_minutes} and {definition.maximum_interval_minutes} minutes.'
        )

    policy = get_or_create_job_policy(job_key)
    policy.enabled = enabled
    policy.trigger_type = 'interval'
    policy.interval_minutes = interval_minutes
    policy.updated_by_user_id = user_id
    if configuration is not None:
        policy.configuration_json = configuration
    policy.next_run_at = calculate_next_run(interval_minutes=interval_minutes) if enabled else None
    db.session.commit()
    return policy

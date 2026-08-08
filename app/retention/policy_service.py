from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app

from app.extensions.db import db
from app.models.lifecycle import DataLifecyclePolicy
from app.retention.types import RetentionPolicy


def resolve_policy(domain: str, fallback: RetentionPolicy) -> RetentionPolicy:
    stored = DataLifecyclePolicy.query.filter_by(domain=domain).first()
    if stored is None:
        return fallback
    return replace(
        fallback,
        enabled=bool(stored.enabled),
        retention_days=max(int(stored.hot_retention_days), 1),
        archive_retention_days=max(int(stored.archive_retention_days), 1),
        batch_size=max(min(int(stored.batch_size), 25000), 100),
        protect_unreviewed=bool(stored.protect_unreviewed),
        protected_max_days=(
            max(int(stored.protected_max_days), 1)
            if stored.protected_max_days is not None
            else fallback.protected_max_days
        ),
        settings=dict(stored.settings_json or fallback.settings or {}),
    )


def get_or_create_policy(domain: str, fallback: RetentionPolicy) -> DataLifecyclePolicy:
    stored = DataLifecyclePolicy.query.filter_by(domain=domain).first()
    if stored is not None:
        return stored
    stored = DataLifecyclePolicy()
    stored.domain = domain
    stored.enabled = fallback.enabled
    stored.hot_retention_days = fallback.retention_days
    stored.archive_retention_days = fallback.archive_retention_days
    stored.batch_size = fallback.batch_size
    stored.operation_mode = 'archive_and_cleanup'
    stored.schedule_enabled = True
    stored.schedule_hour = _default_schedule_hour(domain)
    stored.schedule_minute = _default_schedule_minute(domain)
    stored.protect_unreviewed = fallback.protect_unreviewed
    stored.protected_max_days = fallback.protected_max_days
    stored.settings_json = dict(fallback.settings or {})
    db.session.add(stored)
    db.session.commit()
    return stored


def update_policy(
    *,
    domain: str,
    fallback: RetentionPolicy,
    enabled: bool,
    hot_retention_days: int,
    archive_retention_days: int,
    batch_size: int,
    operation_mode: str,
    schedule_enabled: bool,
    schedule_hour: int,
    schedule_minute: int,
    protect_unreviewed: bool,
    protected_max_days: int | None,
    settings: dict[str, Any] | None = None,
) -> DataLifecyclePolicy:
    policy = get_or_create_policy(domain, fallback)
    policy.enabled = bool(enabled)
    policy.hot_retention_days = max(int(hot_retention_days), 1)
    policy.archive_retention_days = max(int(archive_retention_days), 1)
    policy.batch_size = max(min(int(batch_size), 25000), 100)
    policy.operation_mode = (
        operation_mode if operation_mode in {'archive_only', 'archive_and_cleanup'} else 'archive_and_cleanup'
    )
    policy.schedule_enabled = bool(schedule_enabled)
    policy.schedule_hour = max(0, min(int(schedule_hour), 23))
    policy.schedule_minute = max(0, min(int(schedule_minute), 59))
    policy.protect_unreviewed = bool(protect_unreviewed)
    policy.protected_max_days = (
        max(int(protected_max_days), policy.hot_retention_days) if protected_max_days is not None else None
    )
    policy.settings_json = dict(settings or policy.settings_json or {})
    db.session.commit()
    return policy


def scheduled_domains(domain_names: list[str]) -> list[str]:
    from app.models.job import JobExecution

    timezone_name = str(current_app.config.get('CELERY_TIMEZONE', 'UTC') or 'UTC')
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo('UTC')
    now_local = datetime.now(UTC).astimezone(zone)
    stored = {
        item.domain: item
        for item in DataLifecyclePolicy.query.filter(DataLifecyclePolicy.domain.in_(domain_names)).all()
    }
    due: list[str] = []
    for name in domain_names:
        policy = stored.get(name)
        if policy is None:
            continue
        if not policy.enabled or not policy.schedule_enabled:
            continue
        scheduled_local = now_local.replace(
            hour=policy.schedule_hour, minute=policy.schedule_minute, second=0, microsecond=0
        )
        if now_local < scheduled_local or now_local >= scheduled_local + timedelta(days=1):
            continue
        scheduled_utc = scheduled_local.astimezone(UTC)
        already_dispatched = JobExecution.query.filter(
            JobExecution.job_type == 'data_lifecycle',
            JobExecution.scope_key == name,
            JobExecution.created_at >= scheduled_utc,
            JobExecution.requested_by_user_id.is_(None),
        ).first()
        if already_dispatched is None:
            due.append(name)
    return due


def _default_schedule_hour(domain: str) -> int:
    if domain == 'operational_activity':
        return max(0, min(int(current_app.config.get('ACTIVITY_RETENTION_SCHEDULE_HOUR', 2)), 23))
    if domain == 'runtime_observation':
        return max(0, min(int(current_app.config.get('RUNTIME_OBSERVATION_RETENTION_SCHEDULE_HOUR', 3)), 23))
    if domain == 'analytics_snapshot':
        return max(0, min(int(current_app.config.get('ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_HOUR', 4)), 23))
    return max(0, min(int(current_app.config.get('JOB_EXECUTION_RETENTION_SCHEDULE_HOUR', 3)), 23))


def _default_schedule_minute(domain: str) -> int:
    if domain == 'operational_activity':
        return max(0, min(int(current_app.config.get('ACTIVITY_RETENTION_SCHEDULE_MINUTE', 15)), 59))
    if domain == 'runtime_observation':
        return max(0, min(int(current_app.config.get('RUNTIME_OBSERVATION_RETENTION_SCHEDULE_MINUTE', 45)), 59))
    if domain == 'analytics_snapshot':
        return max(0, min(int(current_app.config.get('ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_MINUTE', 15)), 59))
    return max(0, min(int(current_app.config.get('JOB_EXECUTION_RETENTION_SCHEDULE_MINUTE', 0)), 59))

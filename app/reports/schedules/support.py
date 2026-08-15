from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app
from sqlalchemy import select

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.object_storage import ObjectStorageSystem
from app.models.report import ReportSchedule
from app.reports.catalog import REPORT_TYPE_OPTIONS

DEFAULT_TIMEZONE = 'Asia/Jakarta'


def get_object_storage_system_options() -> list[dict[str, str]]:
    systems = db.session.scalars(select(ObjectStorageSystem).order_by(ObjectStorageSystem.name.asc())).all()
    return [
        {
            'value': item.id,
            'label': f"{item.name} · {item.environment or 'Unspecified Environment'}",
        }
        for item in systems
    ]


def get_cluster_options() -> list[dict[str, str]]:
    clusters = db.session.scalars(select(Cluster).order_by(Cluster.name.asc())).all()
    return [{'value': item.id, 'label': item.name} for item in clusters]


def get_cluster_map(cluster_ids: list[str]) -> dict[str, str]:
    if not cluster_ids:
        return {}
    clusters = db.session.scalars(select(Cluster).where(Cluster.id.in_(cluster_ids))).all()
    return {item.id: item.name for item in clusters}


def get_schedule_context_map(schedule_ids: list[int]) -> dict[int, dict[str, str]]:
    if not schedule_ids:
        return {}
    schedules = db.session.scalars(select(ReportSchedule).where(ReportSchedule.id.in_(schedule_ids))).all()
    report_icons = {str(item['value']): str(item.get('icon') or 'calendar-clock') for item in REPORT_TYPE_OPTIONS}
    return {
        item.id: {
            'name': item.name,
            'icon': report_icons.get(str(item.report_type), 'calendar-clock'),
        }
        for item in schedules
    }


def get_default_timezone() -> str:
    return str(current_app.config.get('REPORT_SCHEDULE_TIMEZONE', DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE)


def is_valid_run_time(value: str) -> bool:
    try:
        parse_run_time(value)
        return True
    except ValueError:
        return False


def parse_run_time(value: str) -> tuple[int, int]:
    hour_raw, minute_raw = value.split(':', maxsplit=1)
    hour = int(hour_raw)
    minute = int(minute_raw)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError('Invalid run time')
    return hour, minute


def parse_optional_int(value: Any) -> int | None:
    if value in [None, '']:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_valid_timezone(value: str) -> bool:
    try:
        ZoneInfo(value)
        return True
    except ZoneInfoNotFoundError:
        return False


def get_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def format_datetime(value: datetime | None, timezone: str) -> str:
    if value is None:
        return 'Never'
    return value.astimezone(get_timezone(timezone)).strftime('%Y-%m-%d %H:%M %Z')


def get_default_sections(report_type: str) -> list[str]:
    for item in REPORT_TYPE_OPTIONS:
        if item['value'] == report_type:
            return list(item['default_sections'])
    return list(REPORT_TYPE_OPTIONS[0]['default_sections'])


def get_default_sections_by_report_type() -> dict[str, list[str]]:
    return {item['value']: list(item['default_sections']) for item in REPORT_TYPE_OPTIONS}


def get_delivery_channel_options() -> list[dict[str, Any]]:
    from app.reports.notifications import get_report_notification_channel_options

    by_channel: dict[int, dict[str, Any]] = {}
    for domain in ('kubernetes', 'object_storage'):
        for option in get_report_notification_channel_options(domain=domain):
            channel_id = int(option['channel_id'])
            existing = by_channel.setdefault(
                channel_id,
                {**option, 'domains': [], 'selectable': False},
            )
            if bool(option.get('supports_domain')):
                existing['domains'].append(domain)
            existing['selectable'] = bool(existing['selectable'] or option.get('selectable'))
    return list(by_channel.values())


def get_section_options_by_report_type(section_options: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    section_map = {item['value']: item for item in section_options}
    return {
        item['value']: [section_map[section] for section in item['default_sections'] if section in section_map]
        for item in REPORT_TYPE_OPTIONS
    }

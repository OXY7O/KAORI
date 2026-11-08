from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from app.extensions.db import db
from app.models.notification_channel import NotificationChannel, NotificationDelivery
from app.models.report import ReportSchedule


@dataclass(frozen=True, slots=True)
class NotificationChannelUsage:
    delivery_records: int
    report_schedules: int
    report_schedule_names: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return self.delivery_records > 0 or self.report_schedules > 0

    @property
    def message(self) -> str:
        reasons: list[str] = []
        if self.delivery_records:
            reasons.append(
                f'{self.delivery_records} delivery evidence record(s) depend on this channel. '
                'Disable the channel instead so delivery history remains auditable.'
            )
        if self.report_schedules:
            reasons.append(
                f'{self.report_schedules} report schedule(s) still reference this channel. '
                'Remove the channel from those schedules before deleting it.'
            )
        return ' '.join(reasons)


class NotificationChannelRetirementBlocked(ValueError):
    """A terminal retirement must not silently break report schedules or history."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class NotificationChannelDeletionBlocked(ValueError):
    def __init__(self, usage: NotificationChannelUsage) -> None:
        super().__init__(usage.message)
        self.usage = usage


def get_channel_usage(channel_id: int) -> NotificationChannelUsage:
    delivery_records = NotificationDelivery.query.filter_by(channel_id=channel_id).count()
    schedule_rows = ReportSchedule.query.with_entities(
        ReportSchedule.name,
        ReportSchedule.notification_channel_ids,
    ).all()
    schedule_names = tuple(
        str(name or 'Unnamed Schedule')
        for name, channel_ids in schedule_rows
        if channel_id in _normalized_channel_ids(channel_ids)
    )
    return NotificationChannelUsage(
        delivery_records=delivery_records,
        report_schedules=len(schedule_names),
        report_schedule_names=schedule_names,
    )


def channel_usage_map(channel_ids: list[int]) -> dict[int, NotificationChannelUsage]:
    if not channel_ids:
        return {}
    delivery_counts = {
        int(channel_id): int(count)
        for channel_id, count in (
            db.session.query(NotificationDelivery.channel_id, func.count(NotificationDelivery.id))
            .filter(NotificationDelivery.channel_id.in_(channel_ids))
            .group_by(NotificationDelivery.channel_id)
            .all()
        )
    }
    schedule_names: dict[int, list[str]] = {channel_id: [] for channel_id in channel_ids}
    for name, raw_channel_ids in ReportSchedule.query.with_entities(
        ReportSchedule.name,
        ReportSchedule.notification_channel_ids,
    ).all():
        referenced_ids = _normalized_channel_ids(raw_channel_ids)
        for channel_id in referenced_ids.intersection(schedule_names):
            schedule_names[channel_id].append(str(name or 'Unnamed Schedule'))
    return {
        channel_id: NotificationChannelUsage(
            delivery_records=delivery_counts.get(channel_id, 0),
            report_schedules=len(schedule_names[channel_id]),
            report_schedule_names=tuple(schedule_names[channel_id]),
        )
        for channel_id in channel_ids
    }


def retire_channel(channel: NotificationChannel, *, reason: str, user_id: int) -> None:
    """Retire a channel without deleting provider/evidence identity or delivery history."""
    normalized_reason = str(reason or '').strip()
    if not 8 <= len(normalized_reason) <= 500:
        raise NotificationChannelRetirementBlocked('Provide a retirement reason between 8 and 500 characters.')

    # Lock the channel row before the irreversible lifecycle transition.
    locked = db.session.get(NotificationChannel, channel.id, with_for_update=True)
    if locked is None or locked.lifecycle_state != 'active':
        raise NotificationChannelRetirementBlocked('This channel is already retired or unavailable.')
    usage = get_channel_usage(locked.id)
    if usage.report_schedules:
        raise NotificationChannelRetirementBlocked(
            f'{usage.report_schedules} report schedule(s) reference this channel. Remove those references before retirement.'
        )
    locked.enabled = False
    locked.lifecycle_state = 'retired'
    locked.retired_at = datetime.now(UTC)
    locked.retired_by_user_id = user_id
    locked.retirement_reason = normalized_reason
    locked.updated_by_user_id = user_id
    db.session.commit()


def delete_channel(channel: NotificationChannel) -> None:
    if channel.lifecycle_state == 'retired':
        raise NotificationChannelRetirementBlocked('Retired channels are retained for historical audit.')
    usage = get_channel_usage(channel.id)
    if usage.blocked:
        raise NotificationChannelDeletionBlocked(usage)
    db.session.delete(channel)
    db.session.commit()


def _normalized_channel_ids(value: Any) -> set[int]:
    if not isinstance(value, list):
        return set()
    normalized: set[int] = set()
    for item in value:
        try:
            normalized.add(int(item))
        except (TypeError, ValueError):
            continue
    return normalized

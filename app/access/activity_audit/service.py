from __future__ import annotations

from typing import Any

from app.notifications.queries import (
    get_notification_activity_context,
    get_notification_activity_detail,
    get_notification_activity_summary,
)


def get_activity_audit_summary() -> dict[str, int | str]:
    return get_notification_activity_summary()


def build_activity_audit_context(
    *,
    actor_key: str | None,
    page: int,
    per_page: int,
    status: str,
    category: str,
    time_range: str,
    search: str,
    include_summary: bool = True,
) -> dict[str, Any]:
    return get_notification_activity_context(
        actor_key=actor_key,
        page=page,
        per_page=per_page,
        status=status,
        category=category,
        time_range=time_range,
        search=search,
        include_summary=include_summary,
    )


def get_activity_audit_detail(*, notification_id: int) -> dict[str, Any] | None:
    return get_notification_activity_detail(notification_id=notification_id)

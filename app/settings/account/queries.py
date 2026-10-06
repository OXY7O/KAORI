from __future__ import annotations

from app.models import Notification


def recent_authentication_events(user_id: int, *, limit: int = 5) -> list[Notification]:
    return (
        Notification.query.filter(
            Notification.user_id == user_id,
            Notification.event_type == 'authentication',
        )
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )


def authentication_activity_summary(events: list[Notification]) -> dict[str, int]:
    summary = {'total': len(events), 'success': 0, 'failed': 0, 'sign_out': 0}
    for event in events:
        metadata = event.metadata_json or {}
        action = metadata.get('access_action') or ('logout' if event.title == 'User signed out' else 'login')
        if action == 'logout':
            summary['sign_out'] += 1
        elif event.status == 'success':
            summary['success'] += 1
        else:
            summary['failed'] += 1
    return summary

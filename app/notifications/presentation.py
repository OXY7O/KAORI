from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.models.notification import Notification
from app.models.user import User

from .event_catalog import build_event_context, event_label
from .metadata import changed_fields, metadata_items
from .normalization import standardize_activity_text


def _normalize_created_at(created_at: datetime) -> datetime:
    if created_at.tzinfo is None:
        return created_at.replace(tzinfo=UTC)

    return created_at.astimezone(UTC)


def _created_label(created_at: datetime) -> str:
    normalized_created_at = _normalize_created_at(created_at)
    age_seconds = max(
        0,
        int((datetime.now(UTC) - normalized_created_at).total_seconds()),
    )

    if age_seconds < 60:
        return 'Just now'
    if age_seconds < 3600:
        minutes = age_seconds // 60
        return f'{minutes} min ago'
    if age_seconds < 86400:
        hours = age_seconds // 3600
        return f'{hours} hr ago'

    days = age_seconds // 86400
    return f'{days} day ago' if days == 1 else f'{days} days ago'


def _actor_initials(label: str) -> str:
    normalized = re.sub(r'[^A-Za-z0-9 ]+', ' ', label).strip()
    parts = [part for part in normalized.split() if part]

    if not parts:
        return 'US'
    if len(parts) == 1:
        return parts[0][:2].upper()

    return f'{parts[0][0]}{parts[-1][0]}'.upper()


def _auth_source_label(value: str | None) -> str:
    normalized = (value or 'database').strip().lower()
    labels = {
        'database': 'Local',
        'local': 'Local',
        'ldap': 'LDAP',
        'oidc': 'OIDC / SSO',
        'saml': 'SAML / SSO',
        'api_token': 'API Token',
        'system': 'System Service',
    }
    return labels.get(
        normalized,
        normalized.replace('_', ' ').title(),
    )


def _user_label(user: User | None, user_id: int) -> str:
    if user is None:
        return f'User #{user_id}'

    suffix = ' · Deleted' if user.deleted_at is not None else ''
    return f'{user.display_label}{suffix}'


def _serialize_notification(
    notification: Notification,
    *,
    include_metadata: bool,
    user: User | None = None,
) -> dict[str, Any]:
    metadata = notification.metadata_json or {}
    created_at = _normalize_created_at(notification.created_at)
    user_label = _user_label(user, notification.user_id)
    event_context = build_event_context(
        notification.event_type,
        metadata,
        notification.title,
    )

    status_labels = {
        'success': 'Success',
        'warning': 'Warning',
        'error': 'Failed',
        'info': 'Information',
    }

    item: dict[str, Any] = {
        'id': notification.id,
        'user_id': notification.user_id,
        'user_label': user_label,
        'user_email': user.email if user is not None else None,
        'user_initials': _actor_initials(user_label),
        'user_role': user.role_display_name if user is not None else 'Unknown role',
        'user_auth_source': _auth_source_label(user.auth_source if user is not None else None),
        'event_type': notification.event_type,
        'event_label': event_label(notification.event_type),
        'status': notification.status,
        'status_label': status_labels.get(notification.status, 'Information'),
        'title': standardize_activity_text(
            notification.title,
            event_type=notification.event_type,
            status=notification.status,
        )
        or 'Operational activity',
        'message': standardize_activity_text(
            notification.message,
            event_type=notification.event_type,
            status=notification.status,
        )
        or 'The operation was recorded by KAORI.',
        'detail': standardize_activity_text(
            notification.detail,
            event_type=notification.event_type,
            status=notification.status,
        ),
        'action_url': notification.action_url,
        'created_at': created_at,
        'created_label': _created_label(created_at),
        'is_read': notification.is_read,
        'read_label': 'Read' if notification.is_read else 'Unread',
        'synced_count': metadata.get('synced_count'),
        'failed_count': metadata.get('failed_count'),
        'total_count': metadata.get('total_count'),
        'duration_seconds': metadata.get('duration_seconds'),
        'changed_fields': changed_fields(metadata),
        **event_context,
    }

    if include_metadata:
        item['metadata_items'] = metadata_items(
            metadata,
            event_type=notification.event_type,
        )

    return item

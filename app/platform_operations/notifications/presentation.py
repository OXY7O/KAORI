from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.models.notification import Notification
from app.models.user import User
from app.platform_operations.notifications.event_catalog import build_event_context, event_category_for_key, event_label
from app.platform_operations.notifications.metadata import changed_fields, metadata_items
from app.platform_operations.notifications.normalization import standardize_activity_text, standardize_activity_title


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
        'internal': 'KAORI Internal',
        'unauthenticated': 'Unauthenticated',
    }
    return labels.get(
        normalized,
        normalized.replace('_', ' ').title(),
    )


def _user_label(user: User | None, user_id: int | None) -> str:
    if user is None:
        return f'User #{user_id}' if user_id is not None else 'System service'

    suffix = ' · Deleted' if user.deleted_at is not None else ''
    return f'{user.display_label}{suffix}'


_ACTIVITY_EXECUTION_EVIDENCE_KEYS = (
    'total_count',
    'synced_count',
    'failed_count',
    'updated_count',
    'record_count',
    'cleanup_deleted_count',
    'target_count',
    'duration_seconds',
    'response_time_ms',
)
_ACTIVITY_TRACE_REFERENCE_KEYS = (
    'task_id',
    'job_execution_id',
    'job_id',
    'bulk_job_id',
    'archive_id',
    'certificate_id',
)
_ACTIVITY_FAILURE_CONTEXT_KEYS = (
    'failed_clusters',
    'cluster_scope',
    'endpoint',
    'server',
    'failure_code',
    'reason_code',
)
_ACTIVITY_TECHNICAL_EVIDENCE_KEYS = (
    'failure_evidence',
    'error',
    'error_message',
    'exception',
    'traceback',
    'raw_error',
    'failure_detail',
)


def _technical_evidence_value(value: Any) -> str:
    rendered = re.sub(r'\s+', ' ', str(value or '')).strip()
    if not rendered:
        return '-'

    rendered = re.sub(
        r'(?i)(https?://)([^/@\s:]+):([^/@\s]+)@',
        r'\1***:***@',
        rendered,
    )
    rendered = re.sub(
        r'(?i)\b(password|passwd|token|secret|api[_-]?key)=([^&\s,;]+)',
        r'\1=***',
        rendered,
    )
    if len(rendered) > 1200:
        rendered = f'{rendered[:1197].rstrip()}...'
    return rendered


def _activity_failure_type(value: str | None, fallback: str | None = None) -> str:
    normalized = (value or '').lower()
    if any(token in normalized for token in ('nameresolutionerror', 'name resolution', 'failed to resolve', 'dns')):
        return 'Name Resolution'
    if any(token in normalized for token in ('timeout', 'timed out', 'read timed out')):
        return 'Timeout'
    if 'connection refused' in normalized:
        return 'Connection Refused'
    if any(token in normalized for token in ('certificate', 'x509', 'ssl', 'tls')):
        return 'TLS Verification'
    if any(token in normalized for token in ('401', 'unauthorized', 'authentication failed', 'invalid credential')):
        return 'Authentication'
    if any(token in normalized for token in ('403', 'forbidden', 'permission denied')):
        return 'Authorization'
    if any(token in normalized for token in ('connectionerror', 'max retries exceeded', 'connectionpool')):
        return 'Connectivity'
    if fallback:
        return fallback.replace('_', ' ').title()
    return 'Operational Failure'


def _activity_detail_evidence(
    *,
    notification: Notification,
    metadata: dict[str, Any],
    event_context: dict[str, Any],
) -> dict[str, Any]:
    all_metadata_items = metadata_items(
        metadata,
        event_type=notification.event_type,
    )
    items_by_key = {item['key']: item for item in all_metadata_items}

    execution_evidence = [items_by_key[key] for key in _ACTIVITY_EXECUTION_EVIDENCE_KEYS if key in items_by_key]

    trace_references: list[dict[str, Any]] = [
        {
            'key': 'source',
            'label': 'Source',
            'value': event_context['source_label'],
            'is_identifier': False,
            'tone': 'slate',
        },
        {
            'key': 'event_key',
            'label': 'Event Key',
            'value': notification.event_type,
            'is_identifier': True,
            'tone': 'slate',
        },
    ]
    trace_references.extend(items_by_key[key] for key in _ACTIVITY_TRACE_REFERENCE_KEYS if key in items_by_key)

    technical_evidence = [
        {
            'key': key,
            'label': key.replace('_', ' ').title(),
            'value': _technical_evidence_value(metadata[key]),
        }
        for key in _ACTIVITY_TECHNICAL_EVIDENCE_KEYS
        if metadata.get(key) not in (None, '')
    ]

    failure_raw = next(
        (
            str(metadata[key])
            for key in (
                'failure_evidence',
                'error_message',
                'error',
                'exception',
                'traceback',
                'reason',
            )
            if metadata.get(key) not in (None, '')
        ),
        notification.detail or notification.message,
    )
    failure_summary = None
    failure_type = None
    failure_context: list[dict[str, Any]] = []
    if notification.status in {'warning', 'error'}:
        failure_summary = (
            standardize_activity_text(
                failure_raw,
                event_type=notification.event_type,
                status=notification.status,
            )
            or 'The operation requires review.'
        )
        failure_type = _activity_failure_type(
            failure_raw,
            str(metadata.get('failure_code') or metadata.get('reason_code') or '').strip() or None,
        )
        failure_context = [items_by_key[key] for key in _ACTIVITY_FAILURE_CONTEXT_KEYS if key in items_by_key]

    consumed_keys = {
        'event_key',
        'reason',
        *_ACTIVITY_EXECUTION_EVIDENCE_KEYS,
        *_ACTIVITY_TRACE_REFERENCE_KEYS,
        *_ACTIVITY_FAILURE_CONTEXT_KEYS,
        *_ACTIVITY_TECHNICAL_EVIDENCE_KEYS,
    }
    additional_evidence = [item for item in all_metadata_items if item['key'] not in consumed_keys]

    return {
        'execution_evidence': execution_evidence,
        'trace_references': trace_references,
        'technical_evidence': technical_evidence,
        'failure_summary': failure_summary,
        'failure_type': failure_type,
        'failure_context': failure_context,
        'additional_evidence': additional_evidence,
    }


def _serialize_notification(
    notification: Notification,
    *,
    include_metadata: bool,
    user: User | None = None,
) -> dict[str, Any]:
    metadata = notification.metadata_json or {}
    created_at = _normalize_created_at(notification.created_at)
    actor_snapshot = notification.actor_snapshot_json or {}
    actor_type = str(actor_snapshot.get('type') or 'system').strip().lower()
    user_label = str(notification.actor_label or actor_snapshot.get('label') or 'KAORI System').strip()
    actor_email = str(actor_snapshot.get('email') or '').strip() or None
    actor_role = str(actor_snapshot.get('role') or 'System Runtime').strip()
    actor_auth_source = str(actor_snapshot.get('auth_source') or 'internal').strip()
    event_context = build_event_context(
        notification.event_type,
        metadata,
        notification.title,
    )
    persisted_category = event_category_for_key(str(notification.category_key or 'operations'))
    event_context.update(
        category_key=persisted_category['key'],
        category_label=persisted_category['label'],
        category_icon=persisted_category['icon'],
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
        'actor_key': notification.actor_key,
        'actor_type': actor_type,
        'user_label': user_label,
        'user_email': actor_email,
        'user_initials': _actor_initials(user_label),
        'user_role': actor_role,
        'user_auth_source': _auth_source_label(actor_auth_source),
        'event_type': notification.event_type,
        'event_label': event_label(notification.event_type),
        'status': notification.status,
        'status_label': status_labels.get(notification.status, 'Information'),
        'title': standardize_activity_title(
            standardize_activity_text(
                notification.title,
                event_type=notification.event_type,
                status=notification.status,
            )
        )
        or 'Operational Activity',
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
        item.update(
            _activity_detail_evidence(
                notification=notification,
                metadata=metadata,
                event_context=event_context,
            )
        )

    return item

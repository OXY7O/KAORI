from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from flask import has_request_context, session
from sqlalchemy import or_

from app.extensions import db
from app.models.notification import Notification
from app.models.user import User

_ALLOWED_STATUSES = {
    'success',
    'warning',
    'error',
    'info',
}
_NAVIGATION_NOTIFICATION_LIMIT = 8
_ACTIVITY_PER_PAGE_OPTIONS = (5, 10, 25, 50)
_QUICK_ACTION_FEEDBACK_SESSION_KEY = 'quick_action_feedback'

logger = logging.getLogger(__name__)

_RAW_ERROR_PATTERNS = (
    'traceback (most recent call last)',
    'httpconnectionpool(',
    'httpsconnectionpool(',
    'max retries exceeded',
    'newconnectionerror',
    'failed to establish a new connection',
    'connection refused',
    'connection aborted',
    'apiexception',
    'status reason headers body',
    'sqlalchemy.exc.',
    'integrityerror',
    'operationalerror',
    'programmingerror',
    'notfoundexception',
    'exception:',
)


def _activity_failure_message(event_type: str, text: str) -> str:
    normalized = text.lower()

    if any(token in normalized for token in ('timeout', 'timed out', 'read timed out')):
        return 'The operation timed out before the target service responded. Review service availability, network access, and the configured timeout.'
    if any(token in normalized for token in ('certificate', 'ssl', 'tls', 'x509')):
        return 'The secure connection could not be verified. Review the endpoint certificate and TLS verification settings.'
    if any(token in normalized for token in ('401', 'unauthorized', 'authentication failed', 'invalid credential')):
        return 'The target service rejected the configured credentials. Review the authentication settings and try again.'
    if any(token in normalized for token in ('403', 'forbidden', 'permission denied')):
        return 'The configured account does not have permission to complete this operation. Review the assigned access and credentials.'
    if any(token in normalized for token in ('404', 'not found', 'notfound')):
        return 'The requested endpoint or resource was not found. Review the configured address and resource availability.'
    if any(token in normalized for token in ('connection refused', 'max retries exceeded', 'connectionerror', 'httpconnectionpool', 'httpsconnectionpool')):
        return 'KAORI could not reach the configured endpoint. Review the endpoint, network route, service availability, and firewall access.'
    if any(token in normalized for token in ('integrityerror', 'operationalerror', 'sqlalchemy', 'database')):
        return 'KAORI could not complete the database operation. Review database availability and the application logs before retrying.'
    if 'kubernetes' in event_type or event_type.startswith('cluster_'):
        return 'The Kubernetes operation could not be completed. Review API reachability, kubeconfig credentials, TLS settings, and cluster compatibility.'
    if event_type.startswith('prometheus_'):
        return 'The Prometheus operation could not be completed. Review the endpoint, authentication, TLS settings, and service availability.'
    if event_type.startswith('alertmanager_'):
        return 'The Alertmanager operation could not be completed. Review the endpoint, authentication, TLS settings, and service availability.'
    if event_type.startswith('operational_activity_'):
        return 'The activity retention operation could not be completed safely. Review the retention status and worker logs before retrying.'

    return 'The operation could not be completed. Review the related configuration and application logs, then try again.'


def _standardize_activity_text(
    value: str | None,
    *,
    event_type: str,
    status: str,
) -> str | None:
    if value is None:
        return None

    normalized = re.sub(r'\s+', ' ', str(value)).strip()
    if not normalized:
        return None

    lowered = normalized.lower()
    looks_raw = (
        any(pattern in lowered for pattern in _RAW_ERROR_PATTERNS)
        or normalized.startswith(('{', '[', '<'))
        or '\\n' in normalized
        or len(normalized) > 700
    )

    if status in {'error', 'warning'} and looks_raw:
        return _activity_failure_message(event_type, normalized)

    return normalized


def create_notification(
    *,
    user_id: int,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Notification:
    normalized_status = status if status in _ALLOWED_STATUSES else 'info'

    notification = Notification()
    notification.user_id = user_id
    notification.event_type = event_type
    notification.status = normalized_status
    notification.title = _standardize_activity_text(
        title,
        event_type=event_type,
        status=normalized_status,
    ) or 'Operational activity'
    notification.message = _standardize_activity_text(
        message,
        event_type=event_type,
        status=normalized_status,
    ) or 'The operation was recorded by KAORI.'
    notification.detail = _standardize_activity_text(
        detail,
        event_type=event_type,
        status=normalized_status,
    )
    notification.action_url = action_url
    notification.metadata_json = metadata

    db.session.add(notification)
    db.session.commit()

    return notification


def build_quick_action_feedback(
    *,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    action_label: str = 'View details',
    action_icon: str = 'arrow-up-right',
    completed_label: str = 'Completed just now',
    notification_saved: bool = True,
) -> dict[str, Any]:
    """Build the shared top-right operational result payload."""
    return {
        'status': status if status in _ALLOWED_STATUSES else 'info',
        'title': title,
        'message': message,
        'detail': detail,
        'view_url': action_url,
        'action_label': action_label,
        'action_icon': action_icon,
        'completed_label': completed_label,
        'notification_saved': notification_saved,
    }


def queue_quick_action_feedback(feedback: dict[str, Any]) -> None:
    """Persist one operational result across a normal redirect."""
    if not has_request_context():
        return

    session[_QUICK_ACTION_FEEDBACK_SESSION_KEY] = feedback
    session.modified = True


def pop_quick_action_feedback() -> dict[str, Any] | None:
    """Return and clear the pending redirect result for the current request."""
    if not has_request_context():
        return None

    feedback = session.pop(
        _QUICK_ACTION_FEEDBACK_SESSION_KEY,
        None,
    )
    if feedback is not None:
        session.modified = True

    return feedback


def record_operational_activity(
    *,
    user_id: int,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    action_label: str = 'View details',
    action_icon: str = 'arrow-up-right',
    metadata: dict[str, Any] | None = None,
    queue_feedback: bool = False,
) -> dict[str, Any]:
    """Save an activity record and return the matching top-right toast context.

    Notification persistence is deliberately isolated from the primary operation.
    A notification storage failure must not turn a successful cluster or integration
    change into a failed user action.
    """
    notification_saved = True
    normalized_status = status if status in _ALLOWED_STATUSES else 'info'
    normalized_title = _standardize_activity_text(
        title,
        event_type=event_type,
        status=normalized_status,
    ) or 'Operational activity'
    normalized_message = _standardize_activity_text(
        message,
        event_type=event_type,
        status=normalized_status,
    ) or 'The operation was recorded by KAORI.'
    normalized_detail = _standardize_activity_text(
        detail,
        event_type=event_type,
        status=normalized_status,
    )

    try:
        create_notification(
            user_id=user_id,
            event_type=event_type,
            status=normalized_status,
            title=normalized_title,
            message=normalized_message,
            detail=normalized_detail,
            action_url=action_url,
            metadata=metadata,
        )
    except Exception:
        db.session.rollback()
        logger.exception(
            'Initial notification persistence failed for event %s; retrying after rollback.',
            event_type,
        )

        try:
            create_notification(
                user_id=user_id,
                event_type=event_type,
                status=normalized_status,
                title=normalized_title,
                message=normalized_message,
                detail=normalized_detail,
                action_url=action_url,
                metadata=metadata,
            )
        except Exception:
            db.session.rollback()
            notification_saved = False
            logger.exception(
                'Could not persist operational notification for event %s.',
                event_type,
            )

    feedback = build_quick_action_feedback(
        status=normalized_status,
        title=normalized_title,
        message=normalized_message,
        detail=normalized_detail,
        action_url=action_url,
        action_label=action_label,
        action_icon=action_icon,
        notification_saved=notification_saved,
    )

    if queue_feedback:
        queue_quick_action_feedback(
            feedback,
        )

    return feedback


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


def _event_label(event_type: str) -> str:
    return event_type.replace('_', ' ').strip().title() or 'Operational Activity'


def _string_metadata(
    metadata: dict[str, Any],
    *keys: str,
) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue

        normalized = str(value).strip()
        if normalized:
            return normalized

    return None


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


def _event_context(
    event_type: str,
    metadata: dict[str, Any],
    title: str,
) -> dict[str, Any]:
    cluster_name = _string_metadata(metadata, 'cluster_name', 'submitted_name')
    environment = _string_metadata(metadata, 'environment', 'submitted_environment')
    endpoint = _string_metadata(metadata, 'endpoint', 'server')
    task_id = _string_metadata(metadata, 'task_id')

    context: dict[str, Any] = {
        'module_label': 'Operations',
        'target_type': 'Activity',
        'target_name': title,
        'event_icon': 'history',
        'event_tone': 'slate',
        'source_label': 'Administrative action',
        'source_detail': 'KAORI web application',
    }

    if event_type.startswith('cluster_'):
        context.update(
            module_label='Kubernetes Cluster',
            target_type='Cluster',
            target_name=cluster_name or 'Cluster registration',
            event_icon='server',
            event_tone='blue',
        )
    elif event_type.startswith('prometheus_'):
        context.update(
            module_label='Prometheus',
            target_type='Prometheus',
            target_name=cluster_name or endpoint or 'Prometheus integration',
            event_icon='activity',
            event_tone='cyan',
        )
    elif event_type.startswith('alertmanager_'):
        context.update(
            module_label='Alertmanager',
            target_type='Alertmanager',
            target_name=cluster_name or endpoint or 'Alertmanager integration',
            event_icon='siren',
            event_tone='rose',
        )
    elif event_type == 'kubernetes_inventory_sync':
        context.update(
            module_label='Kubernetes Inventory',
            target_type='Inventory',
            target_name=cluster_name or 'All connected clusters',
            event_icon='database',
            event_tone='indigo',
        )
    elif event_type.startswith('operational_activity_'):
        context.update(
            module_label='Activity Retention',
            target_type='Retention',
            target_name=_string_metadata(metadata, 'archive_id', 'domain') or 'Operational activity archive',
            event_icon='archive',
            event_tone='violet',
        )

    if task_id:
        context['source_label'] = 'Background task'
        context['source_detail'] = f'Task {task_id}'
    elif event_type.endswith('_connection_test'):
        context['source_label'] = 'Interactive test'
        context['source_detail'] = 'KAORI web action'
    elif event_type == 'kubernetes_inventory_sync':
        context['source_label'] = 'Inventory worker'
        context['source_detail'] = 'Synchronous inventory action'

    context_items = [
        {
            'label': 'Module',
            'value': context['module_label'],
            'tone': 'blue',
        }
    ]

    if environment:
        context_items.append(
            {
                'label': 'Environment',
                'value': environment,
                'tone': 'emerald' if environment.lower() == 'production' else 'amber',
            }
        )

    if cluster_name and context['target_type'] != 'Cluster':
        context_items.append(
            {
                'label': 'Cluster',
                'value': cluster_name,
                'tone': 'indigo',
            }
        )

    context['context_items'] = context_items
    return context


def _changed_fields(metadata: dict[str, Any]) -> list[dict[str, str]]:
    changed_items: list[dict[str, str]] = []
    label_overrides = {
        'name': 'Name',
        'environment': 'Environment',
        'verify_ssl': 'TLS verification',
        'allow_weak_tls': 'Allow weak TLS',
    }

    for key, previous_value in metadata.items():
        if not key.startswith('previous_'):
            continue

        base_key = key.removeprefix('previous_')
        current_candidates = [base_key, f'submitted_{base_key}']
        if base_key == 'name':
            current_candidates.insert(0, 'cluster_name')

        current_value = next(
            (metadata[candidate] for candidate in current_candidates if candidate in metadata),
            None,
        )

        if current_value is None or _metadata_value(previous_value) == _metadata_value(current_value):
            continue

        changed_items.append(
            {
                'label': label_overrides.get(
                    base_key,
                    base_key.replace('_', ' ').title(),
                ),
                'before': _metadata_value(previous_value),
                'after': _metadata_value(current_value),
            }
        )

    return changed_items


def _metadata_value(value: Any) -> str:
    if isinstance(value, dict):
        if not value:
            return '-'
        return ', '.join(
            f'{str(key).replace("_", " ").title()}: {_metadata_value(item)}'
            for key, item in value.items()
        )
    if isinstance(value, list):
        return ', '.join(_metadata_value(item) for item in value) if value else '-'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if value is None:
        return '-'
    return re.sub(r'\s+', ' ', str(value)).strip() or '-'


def _metadata_items(
    metadata: dict[str, Any],
    *,
    event_type: str,
) -> list[dict[str, Any]]:
    preferred_order = (
        'task_id',
        'archive_id',
        'operation_mode',
        'domain',
        'total_count',
        'synced_count',
        'failed_count',
        'record_count',
        'cleanup_deleted_count',
        'failed_clusters',
        'duration_seconds',
        'response_time_ms',
        'version',
        'endpoint',
        'server',
        'auth_type',
        'timeout_seconds',
        'verify_ssl',
        'failure_code',
        'reason',
    )
    label_overrides = {
        'task_id': 'Task ID',
        'archive_id': 'Archive ID',
        'cluster_id': 'Cluster ID',
        'operation_mode': 'Operation mode',
        'total_count': 'Total resources',
        'synced_count': 'Synchronized',
        'failed_count': 'Failed',
        'record_count': 'Archived records',
        'cleanup_deleted_count': 'Cleaned records',
        'duration_seconds': 'Duration',
        'response_time_ms': 'Response time',
        'timeout_seconds': 'Request timeout',
        'verify_ssl': 'TLS verification',
        'failure_code': 'Failure category',
        'reason': 'Failure summary',
        'storage_backend': 'Storage backend',
        'checksum_sha256': 'SHA-256 checksum',
        'size_bytes': 'Archive size',
        'download_kind': 'Downloaded file',
    }
    context_keys = {
        'cluster_name',
        'environment',
        'submitted_name',
        'submitted_environment',
    }

    visible_metadata: dict[str, Any] = {}
    for key, value in metadata.items():
        if key.startswith('previous_') or key in context_keys:
            continue
        if key.startswith('submitted_') and key.removeprefix('submitted_') in metadata:
            continue
        visible_metadata[key] = value

    keys = [key for key in preferred_order if key in visible_metadata]
    keys.extend(sorted(key for key in visible_metadata if key not in preferred_order))

    items: list[dict[str, Any]] = []
    for key in keys:
        value = visible_metadata[key]
        if key in {'reason', 'error', 'error_message'}:
            rendered_value = _standardize_activity_text(
                _metadata_value(value),
                event_type=event_type,
                status='error',
            ) or 'The operation did not complete successfully.'
        elif key == 'duration_seconds':
            rendered_value = f'{_metadata_value(value)} seconds'
        elif key == 'response_time_ms':
            rendered_value = f'{_metadata_value(value)} ms'
        elif key == 'timeout_seconds':
            rendered_value = f'{_metadata_value(value)} seconds'
        elif key == 'size_bytes':
            try:
                size_value = int(value)
                rendered_value = f'{size_value / 1024:.1f} KiB' if size_value < 1024 * 1024 else f'{size_value / (1024 * 1024):.1f} MiB'
            except (TypeError, ValueError):
                rendered_value = _metadata_value(value)
        else:
            rendered_value = _metadata_value(value)

        is_identifier = key.endswith('_id') or key in {'task_id', 'checksum_sha256'}
        items.append(
            {
                'key': key,
                'label': label_overrides.get(key, key.replace('_', ' ').title()),
                'value': rendered_value,
                'is_identifier': is_identifier,
                'tone': 'rose' if key in {'failed_count', 'failure_code', 'reason', 'error', 'error_message'} else 'slate',
            }
        )

    return items


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
    event_context = _event_context(
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
        'event_label': _event_label(notification.event_type),
        'status': notification.status,
        'status_label': status_labels.get(notification.status, 'Information'),
        'title': _standardize_activity_text(
            notification.title,
            event_type=notification.event_type,
            status=notification.status,
        ) or 'Operational activity',
        'message': _standardize_activity_text(
            notification.message,
            event_type=notification.event_type,
            status=notification.status,
        ) or 'The operation was recorded by KAORI.',
        'detail': _standardize_activity_text(
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
        'changed_fields': _changed_fields(metadata),
        **event_context,
    }

    if include_metadata:
        item['metadata_items'] = _metadata_items(
            metadata,
            event_type=notification.event_type,
        )

    return item


def get_navigation_notification_context(
    *,
    user_id: int,
    limit: int = _NAVIGATION_NOTIFICATION_LIMIT,
) -> dict[str, Any]:
    normalized_limit = max(1, min(limit, _NAVIGATION_NOTIFICATION_LIMIT))
    base_query = Notification.query.filter(
        Notification.user_id == user_id,
    )
    unread_count = base_query.filter(
        Notification.read_at.is_(None),
    ).count()
    total_count = base_query.count()

    notifications = (
        base_query.order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .limit(normalized_limit)
        .all()
    )

    return {
        'items': [
            _serialize_notification(
                notification,
                include_metadata=False,
            )
            for notification in notifications
        ],
        'unread_count': unread_count,
        'total_count': total_count,
        'display_limit': normalized_limit,
    }


def _normalize_user_filter(user_id: int | None) -> int | None:
    if user_id is None or user_id <= 0:
        return None
    return user_id


def get_notification_activity_context(
    *,
    user_id: int | None,
    page: int,
    per_page: int,
    status: str,
    event_type: str,
    read_state: str,
    search: str,
) -> dict[str, Any]:
    normalized_page = max(page, 1)
    normalized_per_page = per_page if per_page in _ACTIVITY_PER_PAGE_OPTIONS else _ACTIVITY_PER_PAGE_OPTIONS[0]
    normalized_status = status if status in _ALLOWED_STATUSES else 'all'
    normalized_event_type = event_type.strip() or 'all'
    normalized_read_state = read_state if read_state in {'all', 'read', 'unread'} else 'all'
    normalized_search = search.strip()
    normalized_user_id = _normalize_user_filter(user_id)

    filtered_query = Notification.query.join(
        User,
        User.id == Notification.user_id,
    )

    if normalized_user_id is not None:
        filtered_query = filtered_query.filter(
            Notification.user_id == normalized_user_id,
        )

    event_type_query = db.session.query(Notification.event_type).join(
        User,
        User.id == Notification.user_id,
    )
    if normalized_user_id is not None:
        event_type_query = event_type_query.filter(
            Notification.user_id == normalized_user_id,
        )

    if normalized_status != 'all':
        filtered_query = filtered_query.filter(
            Notification.status == normalized_status,
        )

    if normalized_event_type != 'all':
        filtered_query = filtered_query.filter(
            Notification.event_type == normalized_event_type,
        )

    if normalized_read_state == 'read':
        filtered_query = filtered_query.filter(
            Notification.read_at.is_not(None),
        )
    elif normalized_read_state == 'unread':
        filtered_query = filtered_query.filter(
            Notification.read_at.is_(None),
        )

    if normalized_search:
        pattern = f'%{normalized_search}%'
        filtered_query = filtered_query.filter(
            or_(
                Notification.title.ilike(pattern),
                Notification.message.ilike(pattern),
                Notification.detail.ilike(pattern),
                Notification.event_type.ilike(pattern),
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.display_name.ilike(pattern),
            )
        )

    pagination = filtered_query.order_by(
        Notification.created_at.desc(),
        Notification.id.desc(),
    ).paginate(
        page=normalized_page,
        per_page=normalized_per_page,
        error_out=False,
    )

    page_user_ids = {notification.user_id for notification in pagination.items}
    page_users = User.query.filter(User.id.in_(page_user_ids)).all() if page_user_ids else []
    users_by_id = {user.id: user for user in page_users}

    event_types = [row[0] for row in (event_type_query.distinct().order_by(Notification.event_type.asc()).all())]

    all_notifications_query = Notification.query
    total_count = all_notifications_query.count()
    unread_count = all_notifications_query.filter(
        Notification.read_at.is_(None),
    ).count()
    success_count = all_notifications_query.filter(
        Notification.status == 'success',
    ).count()
    attention_count = all_notifications_query.filter(
        Notification.status.in_(['warning', 'error']),
    ).count()
    pagination_total = int(pagination.total or 0)
    pagination_pages = max(int(pagination.pages or 0), 1)

    user_options = User.query.order_by(
        User.username.asc(),
        User.id.asc(),
    ).all()

    return {
        'items': [
            _serialize_notification(
                notification,
                include_metadata=True,
                user=users_by_id.get(notification.user_id),
            )
            for notification in pagination.items
        ],
        'summary': {
            'total_count': total_count,
            'unread_count': unread_count,
            'success_count': success_count,
            'attention_count': attention_count,
        },
        'filters': {
            'user_id': normalized_user_id,
            'status': normalized_status,
            'event_type': normalized_event_type,
            'read_state': normalized_read_state,
            'search': normalized_search,
        },
        'user_options': [
            {
                'id': user.id,
                'label': _user_label(user, user.id),
                'email': user.email,
            }
            for user in user_options
        ],
        'event_types': [
            {
                'value': value,
                'label': _event_label(value),
            }
            for value in event_types
        ],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total_items': pagination_total,
            'total_pages': pagination_pages,
            'start_item': ((pagination.page - 1) * pagination.per_page + 1) if pagination_total else 0,
            'end_item': min(pagination.page * pagination.per_page, pagination_total),
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_page': pagination.prev_num,
            'next_page': pagination.next_num,
            'allowed_per_page': _ACTIVITY_PER_PAGE_OPTIONS,
        },
    }


def mark_notification_read(
    *,
    notification_id: int,
    user_id: int,
) -> None:
    notification = Notification.query.filter(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    ).first()

    if notification is None or notification.read_at is not None:
        return

    notification.read_at = datetime.now(UTC)
    db.session.commit()


def mark_all_notifications_read(
    *,
    user_id: int,
) -> None:
    now = datetime.now(UTC)

    Notification.query.filter(
        Notification.user_id == user_id,
        Notification.read_at.is_(None),
    ).update(
        {
            Notification.read_at: now,
        },
        synchronize_session=False,
    )

    db.session.commit()

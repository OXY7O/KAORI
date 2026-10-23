from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import url_for
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.common.pagination import paginate_query
from app.extensions.db import db
from app.integrations.delivery.notification_channels.catalog import (
    domain_event_allowed,
    domain_label,
    domain_options,
    event_severity_scoped,
    event_type_label,
    event_type_options,
)
from app.integrations.delivery.notification_channels.config import (
    notification_delivery_max_attempts,
    notification_delivery_recovery_enabled,
    notification_delivery_retry_delay_seconds,
    notification_delivery_timeout_seconds,
)
from app.integrations.delivery.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationEvent,
    NotificationMessage,
)
from app.integrations.delivery.notification_channels.lifecycle import NotificationChannelUsage, channel_usage_map
from app.integrations.delivery.notification_channels.providers import (
    get_notification_provider,
    provider_catalog,
    provider_labels,
)
from app.integrations.delivery.notification_channels.service_helpers import (
    DeliveryPagination,
    _credential_map,
    _encode_credentials,
    _minimum_severity_label,
    _normalize_severity,
    _reset_channel_validation,
)
from app.models.notification_channel import NotificationChannel, NotificationDelivery
from app.models.report import Report
from app.security.credentials import CredentialEncryptionError, decrypt_credential, encrypt_credential

_PROVIDER_LABELS = provider_labels()
_SEVERITY_RANK = {'info': 1, 'warning': 2, 'critical': 3}
_REPLAY_KEY = '_encrypted_transport_snapshot'


def list_channels() -> list[dict[str, Any]]:
    channels = NotificationChannel.query.order_by(NotificationChannel.name.asc(), NotificationChannel.id.asc()).all()
    return [_channel_view(channel) for channel in channels]


def get_channel(channel_id: int) -> NotificationChannel | None:
    return db.session.get(NotificationChannel, channel_id)


def create_channel(data: NotificationChannelFormInput, *, user_id: int | None) -> NotificationChannel:
    channel = NotificationChannel()
    channel.lifecycle_state = 'active'
    channel.name = data.name
    channel.provider_key = data.provider_key
    channel.enabled = data.enabled
    channel.credential_payload = _encode_credentials(data.credentials)
    channel.destination = data.destination
    channel.provider_config = dict(data.provider_config)
    channel.minimum_severity = data.minimum_severity
    channel.domains = list(data.domains)
    channel.event_types = list(data.event_types)
    channel.test_status = 'not_tested'
    channel.created_by_user_id = user_id
    channel.updated_by_user_id = user_id
    db.session.add(channel)
    db.session.commit()
    return channel


def update_channel(
    channel: NotificationChannel,
    data: NotificationChannelFormInput,
    *,
    user_id: int | None,
) -> NotificationChannel:
    configuration_changed = (
        data.credential_changed
        or data.destination != str(channel.destination or '')
        or dict(data.provider_config) != dict(channel.provider_config or {})
    )
    if channel.lifecycle_state != 'active':
        raise ValueError('Retired channels cannot be modified.')
    channel.name = data.name
    channel.enabled = data.enabled
    if data.credential_changed:
        channel.credential_payload = _encode_credentials(data.credentials)
    channel.destination = data.destination
    channel.provider_config = dict(data.provider_config)
    channel.minimum_severity = data.minimum_severity
    channel.domains = list(data.domains)
    channel.event_types = list(data.event_types)
    channel.updated_by_user_id = user_id
    if configuration_changed:
        _reset_channel_validation(channel)
    db.session.commit()
    return channel


def test_channel(channel: NotificationChannel, *, base_url: str = '') -> DeliveryResult:
    if channel.lifecycle_state != 'active':
        return DeliveryResult(False, 'Retired channels cannot be tested.')
    if not channel.configured:
        result = DeliveryResult(False, f'{_provider_label(channel.provider_key)} configuration is incomplete.')
    else:
        result = _deliver(
            channel,
            NotificationMessage(
                title=f'Notification Channel Test · {channel.name}',
                body=(
                    f'KAORI successfully reached this {_provider_label(channel.provider_key)} destination. '
                    'KAORI can use this channel for the allowed delivery events when it is enabled '
                    'and its policy matches.'
                ),
                severity='info',
                action_url=f'{base_url.rstrip("/")}/integrations/notification-channels' if base_url else None,
                action_label='Open Notification Channels',
            ),
        )
    channel.test_status = 'success' if result.success else 'failed'
    channel.test_message = result.message[:500]
    channel.last_tested_at = datetime.now(UTC)
    db.session.commit()
    return result


def send_channel_preview_message(channel: NotificationChannel, message: NotificationMessage) -> DeliveryResult:
    """Send an operator-requested preview without changing channel validation state."""
    if channel.lifecycle_state != 'active' or not channel.enabled or not channel.configured or channel.test_status != 'success':
        return DeliveryResult(
            False, 'Notification Channel must be enabled, configured, and validated before Send Test.'
        )
    return _deliver(channel, message)


def notification_channel_summary() -> dict[str, Any]:
    channels = NotificationChannel.query.filter_by(lifecycle_state='active').order_by(NotificationChannel.id.asc()).all()
    enabled = [channel for channel in channels if channel.enabled]
    eligible = [channel for channel in enabled if channel.configured and channel.test_status == 'success']
    operational = [channel for channel in eligible if channel.last_delivery_status == 'success']
    delivery_failed = [channel for channel in eligible if channel.last_delivery_status == 'failed']
    validation_failed = [channel for channel in enabled if channel.test_status == 'failed']
    validation_required = [
        channel for channel in enabled if not channel.configured or channel.test_status not in {'success', 'failed'}
    ]
    # The aggregate must not hide an unhealthy enabled destination behind
    # another channel's successful historical delivery.
    if delivery_failed:
        label, tone = 'Degraded', 'warning'
    elif validation_failed:
        label, tone = 'Validation Failed', 'warning'
    elif validation_required:
        label, tone = 'Validation Required', 'warning'
    elif operational:
        label, tone = 'Operational', 'normal'
    elif eligible:
        label, tone = 'Ready', 'info'
    elif channels:
        label, tone = 'Disabled', 'unknown'
    else:
        label, tone = 'Not Configured', 'unknown'
    return {
        'label': label,
        'tone': tone,
        'total': len(channels),
        'enabled': len(enabled),
        'eligible': len(eligible),
        'operational': len(operational),
        'failed': len(delivery_failed) + len(validation_failed),
        'provider_labels': sorted({_provider_label(channel.provider_key) for channel in channels}),
    }


def notification_overview_metrics() -> dict[str, Any]:
    """Summarize committed channel lifecycle and delivery evidence, never live providers."""
    archived = NotificationChannel.query.filter_by(lifecycle_state='retired').count()
    outcome_rows = (
        db.session.query(NotificationDelivery.status, func.count(NotificationDelivery.id))
        .group_by(NotificationDelivery.status)
        .all()
    )
    outcomes = {str(status): int(count) for status, count in outcome_rows}
    for status in ('sent', 'failed', 'queued', 'skipped'):
        outcomes.setdefault(status, 0)
    recent = (
        NotificationDelivery.query
        .order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())
        .limit(5)
        .all()
    )
    return {
        'archived': int(archived),
        'delivery_total': sum(outcomes.values()),
        'outcomes': outcomes,
        'recent': [
            {
                'id': delivery.id,
                'channel_name': delivery.channel.name,
                'event_label': event_type_label(delivery.event_type),
                'status_label': {
                    'sent': 'Delivered', 'failed': 'Failed',
                    'queued': 'Queued', 'skipped': 'Skipped',
                }.get(delivery.status, 'Unknown'),
                'status_tone': {
                    'sent': 'normal', 'failed': 'warning',
                    'queued': 'info', 'skipped': 'unknown',
                }.get(delivery.status, 'unknown'),
                'created_at': delivery.created_at,
            }
            for delivery in recent
        ],
    }


def get_notification_channels_payload(
    *,
    channel_page: int = 1,
    channel_per_page: int = 5,
    channel_search: str = '',
    channel_provider: str = '',
    channel_state: str = '',
    channel_lifecycle: str = 'active',
    delivery_pagination: DeliveryPagination = DeliveryPagination(),
    delivery_event_key: str = '',
    delivery_provider: str = '',
    delivery_domain: str = '',
    delivery_severity: str = '',
    delivery_status: str = '',
    can_view_reports: bool = False,
) -> dict[str, Any]:
    normalized_channel_search = str(channel_search or '').strip()[:160]
    normalized_provider = str(channel_provider or '').strip().lower()
    normalized_provider = normalized_provider if normalized_provider in _PROVIDER_LABELS else ''
    normalized_state = str(channel_state or '').strip().lower()
    normalized_state = normalized_state if normalized_state in {'enabled', 'disabled'} else ''
    normalized_lifecycle = 'retired' if channel_lifecycle == 'retired' else 'active'
    if normalized_lifecycle == 'retired':
        normalized_state = ''
    channel_rows, channel_pagination = _channel_registry_page(
        page=channel_page,
        per_page=channel_per_page,
        search=normalized_channel_search,
        provider=normalized_provider,
        state=normalized_state,
        lifecycle=normalized_lifecycle,
    )
    normalized_delivery_key = str(delivery_event_key or '').strip()[:255]
    normalized_delivery_provider = str(delivery_provider or '').strip().lower()
    normalized_delivery_provider = (
        normalized_delivery_provider if normalized_delivery_provider in _PROVIDER_LABELS else ''
    )
    normalized_delivery_domain = str(delivery_domain or '').strip()
    normalized_delivery_domain = (
        normalized_delivery_domain
        if normalized_delivery_domain in {item['value'] for item in domain_options()}
        else ''
    )
    normalized_delivery_severity = str(delivery_severity or '').strip().lower()
    normalized_delivery_severity = (
        normalized_delivery_severity if normalized_delivery_severity in _SEVERITY_RANK else ''
    )
    normalized_delivery_status = str(delivery_status or '').strip().lower()
    normalized_delivery_status = (
        normalized_delivery_status if normalized_delivery_status in {'queued', 'sent', 'failed', 'skipped'} else ''
    )
    delivery_rows, delivery_window = _delivery_registry_page(
        page=delivery_pagination.page,
        per_page=delivery_pagination.per_page,
        event_key=normalized_delivery_key,
        provider=normalized_delivery_provider,
        domain=normalized_delivery_domain,
        severity=normalized_delivery_severity,
        status=normalized_delivery_status,
        can_view_reports=can_view_reports,
    )
    summary = notification_channel_summary()
    provider_counts = {
        str(provider_key): int(count)
        for provider_key, count in (
            db.session.query(NotificationChannel.provider_key, func.count(NotificationChannel.id))
            .group_by(NotificationChannel.provider_key)
            .all()
        )
    }
    providers = [
        {
            **item,
            'status': 'Available',
            'tone': 'normal',
            'configured_count': provider_counts.get(str(item['key']), 0),
        }
        for item in provider_catalog()
    ]
    return {
        'summary': summary,
        'overview': notification_overview_metrics(),
        'posture': {'label': summary['label'], 'tone': summary['tone']},
        'channels': channel_rows,
        'channel_pagination': channel_pagination,
        'channel_lifecycle': normalized_lifecycle,
        'channel_filters': {
            'search': normalized_channel_search,
            'provider': normalized_provider,
            'state': normalized_state,
        },
        'deliveries': delivery_rows,
        'delivery_pagination': delivery_window,
        'delivery_filter': normalized_delivery_key,
        'delivery_filters': {
            'provider': normalized_delivery_provider,
            'domain': normalized_delivery_domain,
            'severity': normalized_delivery_severity,
            'status': normalized_delivery_status,
        },
        'delivery_filters_active': any(
            (
                normalized_delivery_key,
                normalized_delivery_provider,
                normalized_delivery_domain,
                normalized_delivery_severity,
                normalized_delivery_status,
            )
        ),
        'providers': providers,
        'domain_options': domain_options(),
        'event_type_options': event_type_options(),
        'severity_options': [
            {'value': 'critical', 'label': 'Critical only'},
            {'value': 'warning', 'label': 'Warning and Critical'},
            {'value': 'info', 'label': 'Info, Warning, and Critical'},
        ],
        'smtp_security_options': [
            {'value': 'starttls', 'label': 'STARTTLS'},
            {'value': 'tls', 'label': 'TLS / SMTPS'},
            {'value': 'none', 'label': 'None / trusted relay'},
        ],
        'delivery_contract': {
            'events': f'{len(event_type_options())} governed event types',
            'retry': (
                f'Up to {notification_delivery_max_attempts()} attempts; '
                + ('recovery worker enabled' if notification_delivery_recovery_enabled() else 'recovery worker off')
            ),
            'deduplication': 'Per channel and emitted event identity',
            'ownership': 'Consumers emit governed events; Notification Channels delivers.',
        },
    }


def _channel_registry_page(
    *, page: int, per_page: int, search: str = '', provider: str = '', state: str = '',
    lifecycle: str = 'active',
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = NotificationChannel.query.filter_by(lifecycle_state=lifecycle)
    if search:
        query = query.filter(func.lower(NotificationChannel.name).contains(search.lower(), autoescape=True))
    if provider:
        query = query.filter(NotificationChannel.provider_key == provider)
    if state == 'enabled':
        query = query.filter(NotificationChannel.enabled.is_(True))
    elif state == 'disabled':
        query = query.filter(NotificationChannel.enabled.is_(False))
    query = query.order_by(NotificationChannel.name.asc(), NotificationChannel.id.asc())
    rows, pagination = paginate_query(query, page=page, per_page=per_page)
    usage_map = channel_usage_map([channel.id for channel in rows])
    return [_channel_view(channel, usage=usage_map.get(channel.id)) for channel in rows], pagination


def _delivery_registry_page(
    *,
    page: int,
    per_page: int,
    event_key: str = '',
    provider: str = '',
    domain: str = '',
    severity: str = '',
    status: str = '',
    can_view_reports: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = NotificationDelivery.query
    if event_key:
        query = query.filter(NotificationDelivery.event_key == event_key)
    if provider:
        query = query.filter(NotificationDelivery.channel.has(NotificationChannel.provider_key == provider))
    if domain:
        query = query.filter(NotificationDelivery.domain == domain)
    if severity:
        query = query.filter(NotificationDelivery.severity == severity)
    if status:
        query = query.filter(NotificationDelivery.status == status)
    query = query.order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())
    rows, pagination = paginate_query(query, page=page, per_page=per_page)
    # An exact, permissioned page-local read: no per-delivery report query.
    report_ids = (
        {report_id for row in rows if (report_id := _report_id_for_delivery(row)) is not None}
        if can_view_reports
        else set()
    )
    report_lookup = (
        {report.id: report for report in Report.query.filter(Report.id.in_(report_ids)).all()} if report_ids else {}
    )
    return [
        {
            **_delivery_view(row),
            'report_source_url': _report_source_url(row, report_lookup) if can_view_reports else None,
        }
        for row in rows
    ], pagination


def _report_id_for_delivery(delivery: NotificationDelivery) -> int | None:
    """Trust only the exact source-owned report identity from a committed delivery."""
    if delivery.event_type != 'report.generated' or delivery.asset_type != 'report':
        return None
    report_id = str(delivery.asset_key or '')
    if not report_id.isascii() or not report_id.isdecimal() or len(report_id) > 18:
        return None
    if delivery.event_key != f'report.generated:{report_id}':
        return None
    return int(report_id)


def _report_source_url(delivery: NotificationDelivery, report_lookup: dict[int, Report]) -> str | None:
    report_id = _report_id_for_delivery(delivery)
    if report_id is None or report_id not in report_lookup:
        return None
    return url_for('reports.generated_report_detail', report_id=report_id)


def _provider_label(provider_key: str) -> str:
    return _PROVIDER_LABELS.get(provider_key, provider_key.replace('_', ' ').title())


def dispatch_alert_notification(
    *,
    domain: str,
    asset_type: str,
    asset_key: str,
    asset_name: str,
    alert: dict[str, Any],
    recommendations: list[dict[str, Any]] | None = None,
    base_url: str = '',
) -> dict[str, int]:
    """Deliver one first-seen active alert per channel/event identity."""
    severity = _normalize_severity(alert.get('severity'))
    event_key = _event_key(domain=domain, asset_key=asset_key, alert=alert)
    channels = NotificationChannel.query.filter_by(enabled=True, lifecycle_state='active').order_by(NotificationChannel.id.asc()).all()
    stats = {'eligible': 0, 'sent': 0, 'failed': 0, 'retried': 0, 'duplicate': 0, 'skipped': 0}
    max_attempts = notification_delivery_max_attempts()
    for channel in channels:
        if not _channel_matches(
            channel,
            domain=domain,
            severity=severity,
            event_type='alert_intelligence.active_alert',
        ):
            stats['skipped'] += 1
            continue
        stats['eligible'] += 1
        delivery = (
            NotificationDelivery.query.filter_by(channel_id=channel.id, event_key=event_key)
            .with_for_update(skip_locked=True)
            .first()
        )
        if delivery is not None:
            if delivery.status == 'sent':
                stats['duplicate'] += 1
                continue
            if delivery.status != 'failed' or delivery.attempt_count >= max_attempts:
                stats['skipped'] += 1
                continue
        else:
            delivery = NotificationDelivery()
            delivery.channel_id = channel.id
            delivery.event_key = event_key
            delivery.event_type = 'alert_intelligence.active_alert'
            delivery.domain = domain
            delivery.asset_type = asset_type
            delivery.asset_key = str(asset_key)
            delivery.severity = severity
            delivery.status = 'queued'
            delivery.payload_json = {
                'asset_name': asset_name,
                'alert_name': str(alert.get('name') or 'Unknown Alert'),
                'source': str(alert.get('source') or '-'),
                'target': str(alert.get('target') or '-'),
                'recommendation_count': len(recommendations or []),
            }
            db.session.add(delivery)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                stats['duplicate'] += 1
                continue
        message = _alert_message(
            domain=domain,
            asset_key=str(asset_key),
            asset_name=asset_name,
            alert=alert,
            recommendations=recommendations or [],
            base_url=base_url,
        )
        if delivery.attempt_count and _REPLAY_KEY in (delivery.payload_json or {}):
            original = _replay_message(delivery, channel)
            if original is None:
                stats['skipped'] += 1
                db.session.rollback()
                continue
            message = original
        if delivery.attempt_count:
            stats['retried'] += 1
        _begin_delivery_attempt(delivery, channel, message)
        result = _deliver(channel, message)
        _record_delivery_outcome(delivery, channel, result)
        if result.success:
            stats['sent'] += 1
        else:
            stats['failed'] += 1
    return stats


def dispatch_matching_notification_event(*, event: NotificationEvent) -> dict[str, Any]:
    """Deliver one governed event to every validated channel that explicitly allows it."""
    channel_ids = [
        channel.id
        for channel in NotificationChannel.query.filter_by(enabled=True, lifecycle_state='active').order_by(NotificationChannel.id.asc()).all()
        if _channel_matches_event(
            channel,
            domain=event.domain,
            event_type=event.event_type,
            severity=event.severity,
        )
    ]
    return dispatch_notification_event(channel_ids=channel_ids, event=event)


def list_event_channel_options(
    *,
    event_type: str,
    domain: str | None = None,
    severity: str | None = None,
) -> list[dict[str, Any]]:
    """Return configured channel instances for one consumer event contract."""
    channels = NotificationChannel.query.filter_by(lifecycle_state='active').order_by(NotificationChannel.name.asc(), NotificationChannel.id.asc()).all()
    options: list[dict[str, Any]] = []
    for channel in channels:
        supports_event = event_type in (channel.event_types or [])
        supports_domain = domain is None or (
            domain in (channel.domains or []) and domain_event_allowed(domain, event_type)
        )
        supports_severity = (
            severity is None
            or not event_severity_scoped(event_type)
            or _SEVERITY_RANK.get(_normalize_severity(severity), 0) >= _SEVERITY_RANK.get(channel.minimum_severity, 2)
        )
        selectable = bool(
            channel.enabled
            and channel.configured
            and channel.test_status == 'success'
            and supports_event
            and supports_domain
            and supports_severity
        )
        provider = get_notification_provider(channel.provider_key)
        options.append(
            {
                'value': str(channel.id),
                'channel_id': channel.id,
                'label': channel.name,
                'provider': _provider_label(channel.provider_key),
                'provider_icon': provider.icon if provider is not None else 'send',
                'destination': channel.destination or '-',
                'status': channel.display_status,
                'tone': _channel_view(channel)['tone'],
                'selectable': selectable,
                'supports_event': supports_event,
                'supports_domain': supports_domain,
                'supports_severity': supports_severity,
            }
        )
    return options


def dispatch_notification_event(*, channel_ids: list[int], event: NotificationEvent) -> dict[str, Any]:
    """Deliver one governed event to explicitly selected channel instances."""
    normalized_ids = list(dict.fromkeys(value for value in channel_ids if int(value) > 0))
    stats: dict[str, Any] = {
        'requested': len(normalized_ids),
        'successful': 0,
        'failed': 0,
        'skipped': 0,
        'duplicate': 0,
        'results': [],
    }
    max_attempts = notification_delivery_max_attempts()
    for channel_id in normalized_ids:
        channel = db.session.get(NotificationChannel, channel_id)
        if channel is None:
            stats['skipped'] += 1
            stats['results'].append(
                {
                    'channel_id': channel_id,
                    'channel': f'Channel {channel_id}',
                    'provider': '-',
                    'status': 'skipped',
                    'message': 'Notification channel no longer exists.',
                }
            )
            continue
        if not _channel_matches_event(
            channel,
            domain=event.domain,
            event_type=event.event_type,
            severity=event.severity,
        ):
            stats['skipped'] += 1
            stats['results'].append(
                {
                    'channel_id': channel.id,
                    'channel': channel.name,
                    'provider': _provider_label(channel.provider_key),
                    'status': 'skipped',
                    'message': 'Channel is disabled, unvalidated, or not allowed for this event/domain.',
                }
            )
            continue
        delivery = (
            NotificationDelivery.query.filter_by(channel_id=channel.id, event_key=event.event_key)
            .with_for_update(skip_locked=True)
            .first()
        )
        if delivery is not None:
            if delivery.status == 'sent':
                stats['duplicate'] += 1
                stats['skipped'] += 1
                stats['results'].append(
                    {
                        'channel_id': channel.id,
                        'channel': channel.name,
                        'provider': _provider_label(channel.provider_key),
                        'status': 'skipped',
                        'message': 'This event was already delivered to the channel.',
                    }
                )
                continue
            if delivery.status != 'failed' or delivery.attempt_count >= max_attempts:
                stats['skipped'] += 1
                stats['results'].append(
                    {
                        'channel_id': channel.id,
                        'channel': channel.name,
                        'provider': _provider_label(channel.provider_key),
                        'status': 'skipped',
                        'message': 'Delivery is not eligible for another attempt.',
                    }
                )
                continue
        else:
            delivery = NotificationDelivery()
            delivery.channel_id = channel.id
            delivery.event_key = event.event_key
            delivery.event_type = event.event_type
            delivery.domain = event.domain
            delivery.asset_type = event.asset_type
            delivery.asset_key = str(event.asset_key)
            delivery.severity = _normalize_severity(event.severity)
            delivery.status = 'queued'
            delivery.payload_json = dict(event.payload)
            db.session.add(delivery)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                stats['duplicate'] += 1
                stats['skipped'] += 1
                continue
        message = event.message
        if delivery.attempt_count and _REPLAY_KEY in (delivery.payload_json or {}):
            original = _replay_message(delivery, channel)
            if original is None:
                db.session.rollback()
                stats['skipped'] += 1
                stats['results'].append(
                    {
                        'channel_id': channel.id,
                        'channel': channel.name,
                        'provider': _provider_label(channel.provider_key),
                        'status': 'skipped',
                        'message': 'Committed delivery cannot replay after channel transport changes.',
                    }
                )
                continue
            message = original
        _begin_delivery_attempt(delivery, channel, message)
        result = _deliver(channel, message)
        _record_delivery_outcome(delivery, channel, result)
        result_status = 'success' if result.success else 'failed'
        if result.success:
            stats['successful'] += 1
        else:
            stats['failed'] += 1
        stats['results'].append(
            {
                'channel_id': channel.id,
                'channel': channel.name,
                'provider': _provider_label(channel.provider_key),
                'status': result_status,
                'message': result.message,
            }
        )
    return stats


def _transport_snapshot(channel: NotificationChannel, message: NotificationMessage) -> str:
    """Commit an encrypted, immutable replay envelope without exporting provider secrets."""
    return (
        encrypt_credential(
            json.dumps(
                {
                    'channel': {
                        'provider_key': channel.provider_key,
                        'destination': channel.destination,
                        'provider_config': channel.provider_config,
                        'credential_payload': channel.credential_payload,
                    },
                    'message': {
                        'title': message.title,
                        'body': message.body,
                        'severity': message.severity,
                        'action_url': message.action_url,
                        'action_label': message.action_label,
                        'content_format': message.content_format,
                    },
                },
                sort_keys=True,
                separators=(',', ':'),
            )
        )
        or ''
    )


def _replay_message(delivery: NotificationDelivery, channel: NotificationChannel) -> NotificationMessage | None:
    """Reject legacy/invalid snapshots and destinations changed since original emission."""
    token = (delivery.payload_json or {}).get(_REPLAY_KEY)
    if not isinstance(token, str) or not token:
        return None
    try:
        raw = json.loads(decrypt_credential(token) or '')
        if not isinstance(raw, dict):
            return None
        current = {
            'provider_key': channel.provider_key,
            'destination': channel.destination,
            'provider_config': channel.provider_config,
            'credential_payload': channel.credential_payload,
        }
        if raw.get('channel') != current or not isinstance(raw.get('message'), dict):
            return None
        snapshot = raw['message']
        return NotificationMessage(
            title=str(snapshot['title']),
            body=str(snapshot['body']),
            severity=str(snapshot['severity']),
            action_url=snapshot.get('action_url'),
            action_label=snapshot.get('action_label'),
            content_format=str(snapshot.get('content_format') or 'plain_text'),
        )
    except (CredentialEncryptionError, ValueError, KeyError, TypeError):
        return None


def _begin_delivery_attempt(
    delivery: NotificationDelivery, channel: NotificationChannel, message: NotificationMessage
) -> None:
    """Durably claim an attempt before any external transport call."""
    payload = dict(delivery.payload_json or {})
    if delivery.attempt_count == 0 or _REPLAY_KEY not in payload:
        payload[_REPLAY_KEY] = _transport_snapshot(channel, message)
        delivery.payload_json = payload
    delivery.status = 'queued'
    delivery.error_message = None
    delivery.attempt_count += 1
    delivery.updated_at = datetime.now(UTC)
    db.session.commit()


def _record_delivery_outcome(
    delivery: NotificationDelivery, channel: NotificationChannel, result: DeliveryResult
) -> None:
    attempted_at = datetime.now(UTC)
    channel.last_delivery_attempt_at = attempted_at
    channel.last_delivery_message = result.message[:500]
    delivery.updated_at = attempted_at
    if result.success:
        delivery.status = 'sent'
        delivery.sent_at = attempted_at
        delivery.provider_message_id = result.provider_message_id
        channel.last_delivery_status = 'success'
        channel.last_delivery_at = attempted_at
    else:
        delivery.status = 'failed'
        delivery.error_message = result.message[:1000]
        channel.last_delivery_status = 'failed'
    db.session.commit()


def recover_notification_deliveries(*, limit: int = 25) -> dict[str, int]:
    """Retry due committed attempts with one PostgreSQL skip-locked claim at a time.

    At-least-once: a crash after provider acceptance but before outcome commit
    can cause a duplicate. Never advertise exactly-once provider delivery.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=notification_delivery_retry_delay_seconds())
    max_attempts = notification_delivery_max_attempts()
    totals = {'claimed': 0, 'sent': 0, 'failed': 0, 'skipped': 0}
    for _ in range(min(max(int(limit), 1), 50)):
        delivery = (
            NotificationDelivery.query.filter(
                NotificationDelivery.status.in_(('failed', 'queued')),
                NotificationDelivery.updated_at <= cutoff,
                or_(
                    NotificationDelivery.attempt_count < max_attempts,
                    NotificationDelivery.status == 'queued',
                ),
            )
            .order_by(NotificationDelivery.updated_at.asc(), NotificationDelivery.id.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if delivery is None:
            break
        channel = delivery.channel
        if channel.lifecycle_state != 'active':
            delivery.status = 'skipped'
            delivery.error_message = 'Replay suppressed: notification channel has been retired.'
            delivery.updated_at = datetime.now(UTC)
            db.session.commit()
            totals['skipped'] += 1
            continue
        if delivery.attempt_count >= max_attempts:
            delivery.status = 'failed'
            delivery.error_message = 'Delivery attempts exhausted; last provider outcome may be unknown.'
            delivery.updated_at = datetime.now(UTC)
            db.session.commit()
            totals['skipped'] += 1
            continue
        message = _replay_message(delivery, channel)
        if message is None or not _channel_matches_event(
            channel, domain=delivery.domain, event_type=delivery.event_type, severity=delivery.severity
        ):
            delivery.status = 'skipped'
            delivery.error_message = (
                'Replay unavailable: source snapshot missing, invalid, or channel policy/transport changed.'
            )
            delivery.updated_at = datetime.now(UTC)
            db.session.commit()
            totals['skipped'] += 1
            continue
        _begin_delivery_attempt(delivery, channel, message)
        totals['claimed'] += 1
        result = _deliver(channel, message)
        _record_delivery_outcome(delivery, channel, result)
        totals['sent' if result.success else 'failed'] += 1
    return totals


def _channel_matches_event(
    channel: NotificationChannel,
    *,
    domain: str,
    event_type: str,
    severity: str | None = None,
) -> bool:
    allowed_events = set(channel.event_types or [])
    if event_type in {'alert_ops.firing', 'alert_ops.resolved'} and 'alert_intelligence.active_alert' in allowed_events:
        allowed_events.add(event_type)
    if not (
        channel.lifecycle_state == 'active'
        and channel.enabled
        and channel.configured
        and channel.test_status == 'success'
        and domain in (channel.domains or [])
        and domain_event_allowed(domain, event_type)
        and event_type in allowed_events
    ):
        return False
    if severity is None or not event_severity_scoped(event_type):
        return True
    return _SEVERITY_RANK.get(_normalize_severity(severity), 0) >= _SEVERITY_RANK.get(channel.minimum_severity, 2)


def recent_delivery_summary(
    *,
    limit: int = 10,
    event_types: tuple[str, ...] | None = None,
    domain: str | None = None,
    asset_key: str | None = None,
) -> list[dict[str, Any]]:
    query = NotificationDelivery.query
    if event_types:
        query = query.filter(NotificationDelivery.event_type.in_(event_types))
    if domain:
        query = query.filter(NotificationDelivery.domain == domain)
    if asset_key:
        query = query.filter(NotificationDelivery.asset_key == asset_key)
    rows = query.order_by(NotificationDelivery.created_at.desc()).limit(max(limit, 1)).all()
    return [
        {
            'id': row.id,
            'channel_name': row.channel.name,
            'provider': _PROVIDER_LABELS.get(row.channel.provider_key, row.channel.provider_key.title()),
            'event_type': row.event_type,
            'event_label': event_type_label(row.event_type),
            'domain': domain_label(row.domain),
            'asset_key': row.asset_key,
            'severity': row.severity,
            'status': row.status,
            'error_message': row.error_message,
            'created_at': row.created_at,
            'sent_at': row.sent_at,
        }
        for row in rows
    ]


def _delivery_view(delivery: NotificationDelivery) -> dict[str, Any]:
    status_label, status_tone = {
        'sent': ('Delivered', 'normal'),
        'failed': ('Failed', 'warning'),
        'queued': ('Queued', 'info'),
        'skipped': ('Skipped', 'unknown'),
    }.get(delivery.status, (delivery.status.replace('_', ' ').title(), 'unknown'))
    channel = delivery.channel
    adapter = get_notification_provider(channel.provider_key)
    return {
        'id': delivery.id,
        'channel_name': channel.name,
        'provider_label': _provider_label(channel.provider_key),
        'provider_icon': adapter.icon if adapter is not None else 'send',
        'event_type': delivery.event_type,
        'event_label': event_type_label(delivery.event_type),
        'domain': delivery.domain,
        'domain_label': domain_label(delivery.domain),
        'asset_type': delivery.asset_type,
        'asset_key': delivery.asset_key,
        'severity': delivery.severity,
        'severity_label': delivery.severity.replace('_', ' ').title(),
        'status': delivery.status,
        'status_label': status_label,
        'status_tone': status_tone,
        'attempt_count': delivery.attempt_count,
        'error_message': delivery.error_message or '',
        'provider_message_id': delivery.provider_message_id or '',
        'created_at': delivery.created_at,
        'sent_at': delivery.sent_at,
        'updated_at': delivery.updated_at,
    }


def _channel_event_type_groups(labels: list[str]) -> list[dict[str, Any]]:
    """Group committed allowed-use labels for display without altering policy."""
    grouped: dict[str, list[str]] = {}
    for label in labels:
        category, separator, event = label.partition(' · ')
        key = category if separator and category else 'Other'
        grouped.setdefault(key, []).append(event if separator and event else label)
    return [{'label': key, 'events': values} for key, values in grouped.items()]


def _channel_view(
    channel: NotificationChannel,
    *,
    usage: NotificationChannelUsage | None = None,
) -> dict[str, Any]:
    usage = usage or NotificationChannelUsage(0, 0, ())
    status = channel.display_status
    if status == 'Operational':
        tone = 'normal'
    elif status == 'Ready':
        tone = 'info'
    elif status in {
        'Validation Required',
        'Configuration Required',
        'Validation Failed',
        'Delivery Failed',
    }:
        tone = 'warning'
    else:
        tone = 'unknown'
    adapter = get_notification_provider(channel.provider_key)
    event_type_labels = [event_type_label(value) for value in (channel.event_types or [])]
    last_delivery_label, last_delivery_tone = {
        'success': ('Delivered', 'normal'),
        'failed': ('Failed', 'warning'),
        'never': ('Not Delivered', 'unknown'),
    }.get(channel.last_delivery_status, ('Unknown', 'unknown'))
    return {
        'id': channel.id,
        'name': channel.name,
        'provider_key': channel.provider_key,
        'provider_label': _provider_label(channel.provider_key),
        'provider_icon': adapter.icon if adapter is not None else 'send',
        'enabled': channel.enabled,
        'lifecycle_state': channel.lifecycle_state,
        'retired_at': channel.retired_at,
        'retired_by_user_id': channel.retired_by_user_id,
        'retirement_reason': channel.retirement_reason or '',
        'configured': channel.configured,
        'destination': channel.destination or '-',
        'destination_label': channel.destination or '-',
        'minimum_severity': channel.minimum_severity,
        'minimum_severity_label': _minimum_severity_label(channel.minimum_severity),
        'domains': list(channel.domains or []),
        'domain_labels': [domain_label(value) for value in (channel.domains or [])],
        'event_types': list(channel.event_types or []),
        'event_type_labels': event_type_labels,
        'event_type_groups': _channel_event_type_groups(event_type_labels),
        'status': status,
        'tone': tone,
        'test_status': channel.test_status,
        'test_message': channel.test_message or '',
        'last_tested_at': channel.last_tested_at,
        'last_delivery_status': channel.last_delivery_status,
        'last_delivery_label': last_delivery_label,
        'last_delivery_tone': last_delivery_tone,
        'last_delivery_message': channel.last_delivery_message or '',
        'last_delivery_attempt_at': channel.last_delivery_attempt_at,
        'last_delivery_at': channel.last_delivery_at,
        'credential_configured': bool(channel.credential_payload),
        'delete_blocked': usage.blocked,
        'delete_reason': usage.message,
        'delivery_record_count': usage.delivery_records,
        'report_schedule_count': usage.report_schedules,
        'report_schedule_names': list(usage.report_schedule_names),
    }


def _deliver(channel: NotificationChannel, message: NotificationMessage) -> DeliveryResult:
    if channel.lifecycle_state != 'active':
        return DeliveryResult(False, 'Provider delivery is forbidden for retired notification channels.')
    adapter = get_notification_provider(channel.provider_key)
    if adapter is None:
        return DeliveryResult(False, f'Unsupported notification provider: {channel.provider_key}.')
    return adapter.sender(
        _credential_map(channel),
        str(channel.destination or ''),
        dict(channel.provider_config or {}),
        message,
        notification_delivery_timeout_seconds(),
    )


def _channel_matches(
    channel: NotificationChannel,
    *,
    domain: str,
    severity: str,
    event_type: str,
) -> bool:
    return _channel_matches_event(
        channel,
        domain=domain,
        event_type=event_type,
        severity=severity,
    )


def _event_key(*, domain: str, asset_key: str, alert: dict[str, Any]) -> str:
    fingerprint = str(alert.get('fingerprint') or '').strip()
    starts_at = str(alert.get('starts_at') or '').strip()
    if fingerprint:
        identity = '|'.join(value for value in (fingerprint, starts_at) if value)
    else:
        identity = '|'.join(
            [
                str(alert.get('source') or ''),
                str(alert.get('name') or ''),
                str(alert.get('target') or ''),
                str(alert.get('state') or alert.get('status') or ''),
            ]
        )
    import hashlib

    digest = hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]
    return f'alert:{domain}:{asset_key}:{digest}'


def _alert_message(
    *,
    domain: str,
    asset_key: str,
    asset_name: str,
    alert: dict[str, Any],
    recommendations: list[dict[str, Any]],
    base_url: str,
) -> NotificationMessage:
    name = str(alert.get('name') or 'Unknown Alert')
    severity = _normalize_severity(alert.get('severity'))
    state = str(alert.get('state') or alert.get('status') or 'active').title()
    target = str(alert.get('target') or '-').strip() or '-'
    source = str(alert.get('source') or '-').strip() or '-'
    summary = str(alert.get('summary') or alert.get('description') or '-').strip()
    lines = [
        f'Domain: {domain_label(domain)}',
        f'Asset: {asset_name}',
        f'State: {state}',
        f'Target: {target}',
        f'Source: {source}',
        f'Summary: {summary}',
    ]
    if recommendations:
        lines.append(f'Active KAORI recommendations: {len(recommendations)}')
        top = recommendations[0]
        lines.append(f'Guidance: {str(top.get("title") or top.get("summary") or "Review Alert Intelligence")[:240]}')
    action_url = (
        f'{base_url.rstrip("/")}/intelligence/alert-intelligence?domain={domain}&asset={asset_key}'
        if base_url
        else None
    )
    return NotificationMessage(
        title=name,
        body='\n'.join(lines),
        severity=severity,
        action_url=action_url,
        action_label='Open Alert Intelligence',
    )

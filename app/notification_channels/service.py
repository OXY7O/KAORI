from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.extensions.db import db
from app.models.notification_channel import NotificationChannel, NotificationDelivery
from app.notification_channels.config import (
    notification_delivery_max_attempts,
    notification_delivery_timeout_seconds,
)
from app.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationEvent,
    NotificationMessage,
)
from app.notification_channels.providers import (
    get_notification_provider,
    provider_catalog,
    provider_labels,
)

_PROVIDER_LABELS = provider_labels()
_SEVERITY_RANK = {'info': 1, 'warning': 2, 'critical': 3}
_DOMAIN_LABELS = {'kubernetes': 'Kubernetes', 'object_storage': 'Object Storage'}
_EVENT_LABELS = {
    'alert_intelligence.active_alert': 'Alert Intelligence · Active Alert',
    'report.generated': 'Scheduled Reports · Report Ready',
    'automation.approval_required': 'Automation Control · Approval Required',
    'automation.execution_started': 'Automation Control · Execution Started',
    'automation.execution_completed': 'Automation Control · Execution Completed',
    'automation.execution_failed': 'Automation Control · Execution Failed',
    'automation.verification_failed': 'Automation Control · Verification Failed',
}


def list_channels() -> list[dict[str, Any]]:
    channels = NotificationChannel.query.order_by(NotificationChannel.name.asc(), NotificationChannel.id.asc()).all()
    return [_channel_view(channel) for channel in channels]


def get_channel(channel_id: int) -> NotificationChannel | None:
    return db.session.get(NotificationChannel, channel_id)


def create_channel(data: NotificationChannelFormInput, *, user_id: int | None) -> NotificationChannel:
    channel = NotificationChannel(
        name=data.name,
        provider_key=data.provider_key,
        enabled=data.enabled,
        credential_payload=_encode_credentials(data.credentials),
        destination=data.destination,
        provider_config=dict(data.provider_config),
        minimum_severity=data.minimum_severity,
        domains=list(data.domains),
        event_types=list(data.event_types),
        test_status='not_tested',
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
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


def delete_channel(channel: NotificationChannel) -> None:
    db.session.delete(channel)
    db.session.commit()


def test_channel(channel: NotificationChannel, *, base_url: str = '') -> DeliveryResult:
    if not channel.configured:
        result = DeliveryResult(False, f'{_provider_label(channel.provider_key)} configuration is incomplete.')
    else:
        result = _deliver(
            channel,
            NotificationMessage(
                title=f'Notification Channel Test · {channel.name}',
                body=(
                    f'KAORI successfully reached this {_provider_label(channel.provider_key)} destination. '
                    'KAORI can use this channel for the allowed delivery events when it is enabled and its policy matches.'
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


def notification_channel_summary() -> dict[str, Any]:
    channels = NotificationChannel.query.order_by(NotificationChannel.id.asc()).all()
    enabled = [channel for channel in channels if channel.enabled]
    eligible = [channel for channel in enabled if channel.configured and channel.test_status == 'success']
    operational = [channel for channel in eligible if channel.last_delivery_status == 'success']
    delivery_failed = [channel for channel in eligible if channel.last_delivery_status == 'failed']
    validation_failed = [channel for channel in enabled if channel.test_status == 'failed']
    if delivery_failed:
        label, tone = 'Degraded', 'warning'
    elif operational:
        label, tone = 'Operational', 'normal'
    elif eligible:
        label, tone = 'Ready', 'info'
    elif validation_failed:
        label, tone = 'Validation Failed', 'warning'
    elif enabled:
        label, tone = 'Validation Required', 'warning'
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


def get_notification_channels_payload() -> dict[str, Any]:
    channels = list_channels()
    summary = notification_channel_summary()
    provider_status = {
        'telegram': ('Bot API', 'Bot token + chat or channel destination.'),
        'email': ('SMTP', 'SMTP server + sender + one or more recipients.'),
        'microsoft_teams': (
            'Teams Workflows',
            'Power Automate webhook URL + human-readable Teams destination label.',
        ),
    }
    providers = []
    for item in provider_catalog():
        transport, configuration = provider_status[item['key']]
        providers.append(
            {
                **item,
                'status': 'Available',
                'tone': 'normal',
                'transport': transport,
                'configuration': configuration,
            }
        )
    return {
        'summary': summary,
        'posture': {'label': summary['label'], 'tone': summary['tone']},
        'channels': channels,
        'providers': providers,
        'domain_options': [{'value': key, 'label': label} for key, label in _DOMAIN_LABELS.items()],
        'event_type_options': [
            {'value': key, 'label': label}
            for key, label in _EVENT_LABELS.items()
        ],
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
            'events': 'Alert Intelligence + Scheduled Reports + Automation Control',
            'retry': f'Up to {notification_delivery_max_attempts()} attempts',
            'deduplication': 'Per channel and emitted event identity',
            'ownership': 'Consumers emit governed events; Notification Channels owns provider delivery.',
        },
    }


def _reset_channel_validation(channel: NotificationChannel) -> None:
    channel.test_status = 'not_tested'
    channel.test_message = 'Destination, credentials, or transport configuration changed. Validate the channel again.'
    channel.last_tested_at = None
    channel.last_delivery_status = 'never'
    channel.last_delivery_message = None
    channel.last_delivery_attempt_at = None
    channel.last_delivery_at = None


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
    channels = NotificationChannel.query.filter_by(enabled=True).order_by(NotificationChannel.id.asc()).all()
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
        delivery = NotificationDelivery.query.filter_by(channel_id=channel.id, event_key=event_key).first()
        if delivery is not None:
            if delivery.status == 'sent':
                stats['duplicate'] += 1
                continue
            if delivery.status != 'failed' or delivery.attempt_count >= max_attempts:
                stats['skipped'] += 1
                continue
            delivery.status = 'queued'
            delivery.error_message = None
            stats['retried'] += 1
        else:
            delivery = NotificationDelivery(
                channel_id=channel.id,
                event_key=event_key,
                event_type='alert_intelligence.active_alert',
                domain=domain,
                asset_type=asset_type,
                asset_key=str(asset_key),
                severity=severity,
                status='queued',
                payload_json={
                    'asset_name': asset_name,
                    'alert_name': str(alert.get('name') or 'Unknown Alert'),
                    'source': str(alert.get('source') or '-'),
                    'target': str(alert.get('target') or '-'),
                    'recommendation_count': len(recommendations or []),
                },
            )
            db.session.add(delivery)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                stats['duplicate'] += 1
                continue
        message = _alert_message(
            domain=domain,
            asset_name=asset_name,
            alert=alert,
            recommendations=recommendations or [],
            base_url=base_url,
        )
        result = _deliver(channel, message)
        delivery.attempt_count += 1
        attempted_at = datetime.now(UTC)
        channel.last_delivery_attempt_at = attempted_at
        channel.last_delivery_message = result.message[:500]
        if result.success:
            delivery.status = 'sent'
            delivery.sent_at = attempted_at
            delivery.provider_message_id = result.provider_message_id
            channel.last_delivery_status = 'success'
            channel.last_delivery_at = attempted_at
            stats['sent'] += 1
        else:
            delivery.status = 'failed'
            delivery.error_message = result.message[:1000]
            channel.last_delivery_status = 'failed'
            stats['failed'] += 1
        db.session.commit()
    return stats


def list_event_channel_options(*, event_type: str, domain: str | None = None) -> list[dict[str, Any]]:
    """Return configured channel instances for one consumer event contract."""
    channels = NotificationChannel.query.order_by(NotificationChannel.name.asc(), NotificationChannel.id.asc()).all()
    options: list[dict[str, Any]] = []
    for channel in channels:
        supports_event = event_type in (channel.event_types or [])
        supports_domain = domain is None or domain in (channel.domains or [])
        selectable = bool(
            channel.enabled
            and channel.configured
            and channel.test_status == 'success'
            and supports_event
            and supports_domain
        )
        options.append(
            {
                'value': str(channel.id),
                'channel_id': channel.id,
                'label': channel.name,
                'provider': _provider_label(channel.provider_key),
                'provider_icon': (
                    get_notification_provider(channel.provider_key).icon
                    if get_notification_provider(channel.provider_key) is not None
                    else 'send'
                ),
                'destination': channel.destination or '-',
                'status': channel.display_status,
                'tone': _channel_view(channel)['tone'],
                'selectable': selectable,
                'supports_event': supports_event,
                'supports_domain': supports_domain,
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
                {'channel_id': channel_id, 'channel': f'Channel {channel_id}', 'provider': '-', 'status': 'skipped', 'message': 'Notification channel no longer exists.'}
            )
            continue
        if not _channel_matches_event(channel, domain=event.domain, event_type=event.event_type):
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
        delivery = NotificationDelivery.query.filter_by(channel_id=channel.id, event_key=event.event_key).first()
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
            delivery.status = 'queued'
            delivery.error_message = None
        else:
            delivery = NotificationDelivery(
                channel_id=channel.id,
                event_key=event.event_key,
                event_type=event.event_type,
                domain=event.domain,
                asset_type=event.asset_type,
                asset_key=str(event.asset_key),
                severity=_normalize_severity(event.severity),
                status='queued',
                payload_json=dict(event.payload),
            )
            db.session.add(delivery)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                stats['duplicate'] += 1
                stats['skipped'] += 1
                continue
        result = _deliver(channel, event.message)
        attempted_at = datetime.now(UTC)
        delivery.attempt_count += 1
        channel.last_delivery_attempt_at = attempted_at
        channel.last_delivery_message = result.message[:500]
        result_status = 'success' if result.success else 'failed'
        if result.success:
            delivery.status = 'sent'
            delivery.sent_at = attempted_at
            delivery.provider_message_id = result.provider_message_id
            channel.last_delivery_status = 'success'
            channel.last_delivery_at = attempted_at
            stats['successful'] += 1
        else:
            delivery.status = 'failed'
            delivery.error_message = result.message[:1000]
            channel.last_delivery_status = 'failed'
            stats['failed'] += 1
        db.session.commit()
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

def _channel_matches_event(channel: NotificationChannel, *, domain: str, event_type: str) -> bool:
    return bool(
        channel.enabled
        and channel.configured
        and channel.test_status == 'success'
        and domain in (channel.domains or [])
        and event_type in (channel.event_types or [])
    )

def recent_delivery_summary(*, limit: int = 10) -> list[dict[str, Any]]:
    rows = NotificationDelivery.query.order_by(NotificationDelivery.created_at.desc()).limit(max(limit, 1)).all()
    return [
        {
            'id': row.id,
            'channel_name': row.channel.name,
            'provider': _PROVIDER_LABELS.get(row.channel.provider_key, row.channel.provider_key.title()),
            'domain': _DOMAIN_LABELS.get(row.domain, row.domain.replace('_', ' ').title()),
            'asset_key': row.asset_key,
            'severity': row.severity,
            'status': row.status,
            'error_message': row.error_message,
            'created_at': row.created_at,
            'sent_at': row.sent_at,
        }
        for row in rows
    ]


def _channel_view(channel: NotificationChannel) -> dict[str, Any]:
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
        'configured': channel.configured,
        'destination': channel.destination or '-',
        'destination_label': channel.destination or '-',
        'minimum_severity': channel.minimum_severity,
        'minimum_severity_label': _minimum_severity_label(channel.minimum_severity),
        'domains': list(channel.domains or []),
        'domain_labels': [
            _DOMAIN_LABELS.get(value, value.replace('_', ' ').title())
            for value in (channel.domains or [])
        ],
        'event_types': list(channel.event_types or []),
        'event_type_labels': [
            _EVENT_LABELS.get(value, value.replace('_', ' ').replace('.', ' ').title())
            for value in (channel.event_types or [])
        ],
        'status': status,
        'tone': tone,
        'test_message': channel.test_message or '',
        'last_tested_at': channel.last_tested_at,
        'last_delivery_status': channel.last_delivery_status,
        'last_delivery_label': last_delivery_label,
        'last_delivery_tone': last_delivery_tone,
        'last_delivery_message': channel.last_delivery_message or '',
        'last_delivery_attempt_at': channel.last_delivery_attempt_at,
        'last_delivery_at': channel.last_delivery_at,
        'credential_configured': bool(channel.credential_payload),
    }


def _deliver(channel: NotificationChannel, message: NotificationMessage) -> DeliveryResult:
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
    if not channel.configured or channel.test_status != 'success':
        return False
    if domain not in (channel.domains or []):
        return False
    if event_type not in (channel.event_types or []):
        return False
    return _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK.get(channel.minimum_severity, 2)


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
        f'Domain: {_DOMAIN_LABELS.get(domain, domain.replace("_", " ").title())}',
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


def _encode_credentials(credentials: dict[str, str]) -> str:
    return json.dumps(credentials, separators=(',', ':'), sort_keys=True)


def _credential_map(channel: NotificationChannel) -> dict[str, str]:
    raw = str(channel.credential_payload or '').strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items() if value is not None}


def _normalize_severity(value: Any) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in {'critical', 'error', 'fatal', 'p1'}:
        return 'critical'
    if normalized in {'warning', 'warn', 'p2'}:
        return 'warning'
    return 'info'


def _minimum_severity_label(value: str) -> str:
    return {
        'critical': 'Critical only',
        'warning': 'Warning and Critical',
        'info': 'Info and above',
    }.get(value, 'Warning and Critical')

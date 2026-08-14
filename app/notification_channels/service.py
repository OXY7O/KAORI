from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.extensions.db import db
from app.models.notification_channel import NotificationChannel, NotificationDelivery
from app.notification_channels.config import (
    notification_delivery_max_attempts,
    notification_delivery_timeout_seconds,
)
from app.notification_channels.contracts import DeliveryResult, NotificationMessage
from app.notification_channels.providers import get_notification_provider, provider_labels

_PROVIDER_LABELS = provider_labels()
_SEVERITY_RANK = {'info': 1, 'warning': 2, 'critical': 3}
_DOMAIN_LABELS = {'kubernetes': 'Kubernetes', 'object_storage': 'Object Storage'}


@dataclass(frozen=True, slots=True)
class TelegramChannelFormInput:
    name: str
    provider_key: str
    enabled: bool
    bot_token: str
    target_chat_id: str
    minimum_severity: str
    domains: tuple[str, ...]


def parse_channel_form(form: Any) -> TelegramChannelFormInput:
    provider_key = str(form.get('provider_key') or 'telegram').strip().lower()
    minimum_severity = str(form.get('minimum_severity') or 'warning').strip().lower()
    domains = tuple(value for value in form.getlist('domains') if value in _DOMAIN_LABELS)
    return TelegramChannelFormInput(
        name=str(form.get('name') or '').strip(),
        provider_key=provider_key,
        enabled=str(form.get('enabled') or '').lower() in {'1', 'true', 'yes', 'on'},
        bot_token=str(form.get('bot_token') or '').strip(),
        target_chat_id=str(form.get('target_chat_id') or '').strip(),
        minimum_severity=minimum_severity if minimum_severity in _SEVERITY_RANK else 'warning',
        domains=domains or ('kubernetes', 'object_storage'),
    )


def validate_channel_input(data: TelegramChannelFormInput, *, existing: NotificationChannel | None = None) -> list[str]:
    errors: list[str] = []
    if not data.name:
        errors.append('Channel name is required.')
    if data.provider_key != 'telegram':
        errors.append('Telegram is the only supported notification provider in the current release.')
    token_available = bool(data.bot_token or (existing is not None and _credential_map(existing).get('bot_token')))
    if not token_available:
        errors.append('Telegram bot token is required.')
    if not data.target_chat_id:
        errors.append('Telegram chat ID or @channel username is required.')
    return errors


def list_channels() -> list[dict[str, Any]]:
    channels = NotificationChannel.query.order_by(NotificationChannel.name.asc(), NotificationChannel.id.asc()).all()
    return [_channel_view(channel) for channel in channels]


def get_channel(channel_id: int) -> NotificationChannel | None:
    return db.session.get(NotificationChannel, channel_id)


def get_channel_form_view(channel: NotificationChannel | None) -> dict[str, Any] | None:
    """Return editable channel metadata without exposing decrypted credentials."""
    if channel is None:
        return None
    view = _channel_view(channel)
    return {
        'id': view['id'],
        'name': view['name'],
        'enabled': view['enabled'],
        'target_chat_id': view['destination'] if view['destination'] != '-' else '',
        'minimum_severity': view['minimum_severity'],
        'domains': view['domains'],
        'credential_configured': view['credential_configured'],
    }


def create_channel(data: TelegramChannelFormInput, *, user_id: int | None) -> NotificationChannel:
    channel = NotificationChannel(
        name=data.name,
        provider_key=data.provider_key,
        enabled=data.enabled,
        credential_payload=_encode_credentials({'bot_token': data.bot_token}),
        destination=data.target_chat_id,
        provider_config={},
        minimum_severity=data.minimum_severity,
        domains=list(data.domains),
        event_types=['alert_intelligence.active_alert'],
        test_status='not_tested',
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.session.add(channel)
    db.session.commit()
    return channel


def update_channel(
    channel: NotificationChannel,
    data: TelegramChannelFormInput,
    *,
    user_id: int | None,
) -> NotificationChannel:
    token_changed = bool(data.bot_token)
    destination_changed = token_changed or data.target_chat_id != str(channel.destination or '')
    channel.name = data.name
    channel.provider_key = data.provider_key
    channel.enabled = data.enabled
    if token_changed:
        channel.credential_payload = _encode_credentials({'bot_token': data.bot_token})
    channel.destination = data.target_chat_id
    channel.minimum_severity = data.minimum_severity
    channel.domains = list(data.domains)
    channel.updated_by_user_id = user_id
    if destination_changed:
        channel.test_status = 'not_tested'
        channel.test_message = 'Destination or credential changed. Validate the channel again.'
        channel.last_tested_at = None
        channel.last_delivery_status = 'never'
        channel.last_delivery_message = None
        channel.last_delivery_attempt_at = None
        channel.last_delivery_at = None
    db.session.commit()
    return channel


def delete_channel(channel: NotificationChannel) -> None:
    db.session.delete(channel)
    db.session.commit()


def test_channel(channel: NotificationChannel, *, base_url: str = '') -> DeliveryResult:
    if not channel.configured:
        result = DeliveryResult(False, 'Telegram bot token and target chat must be configured before testing.')
    else:
        result = _deliver(
            channel,
            NotificationMessage(
                title=f'Notification Channel Test · {channel.name}',
                body=(
                    'KAORI successfully reached this Telegram destination. Alert Intelligence delivery '
                    'can use this channel when it is enabled and its policy matches.'
                ),
                severity='info',
                action_url=f'{base_url.rstrip("/")}/intelligence/alert-intelligence' if base_url else None,
                action_label='Open Alert Intelligence',
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
        'provider_labels': sorted(
            {_PROVIDER_LABELS.get(channel.provider_key, channel.provider_key) for channel in channels}
        ),
    }


def get_notification_channels_payload() -> dict[str, Any]:
    channels = list_channels()
    summary = notification_channel_summary()
    return {
        'summary': summary,
        'posture': {'label': summary['label'], 'tone': summary['tone']},
        'channels': channels,
        'providers': [
            {
                'key': 'telegram',
                'label': 'Telegram',
                'status': 'Available',
                'tone': 'normal',
                'description': 'Send KAORI Alert Intelligence messages through the Telegram Bot API.',
            },
            {
                'key': 'future',
                'label': 'Additional Channels',
                'status': 'Extensible',
                'tone': 'info',
                'description': (
                    'The channel contract is provider-neutral so Slack, Teams, email, or webhook adapters '
                    'can be added without changing Alert Intelligence.'
                ),
            },
        ],
        'domain_options': [{'value': key, 'label': label} for key, label in _DOMAIN_LABELS.items()],
        'severity_options': [
            {'value': 'critical', 'label': 'Critical only'},
            {'value': 'warning', 'label': 'Warning and Critical'},
            {'value': 'info', 'label': 'Info, Warning, and Critical'},
        ],
    }


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
    return {
        'id': channel.id,
        'name': channel.name,
        'provider_key': channel.provider_key,
        'provider_label': _PROVIDER_LABELS.get(channel.provider_key, channel.provider_key.title()),
        'enabled': channel.enabled,
        'configured': channel.configured,
        'destination': channel.destination or '-',
        'target_chat_id': channel.destination or '-',
        'minimum_severity': channel.minimum_severity,
        'minimum_severity_label': _minimum_severity_label(channel.minimum_severity),
        'domains': list(channel.domains or []),
        'domain_labels': [
            _DOMAIN_LABELS.get(value, value.replace('_', ' ').title())
            for value in (channel.domains or [])
        ],
        'status': status,
        'tone': tone,
        'test_message': channel.test_message or '',
        'last_tested_at': channel.last_tested_at,
        'last_delivery_status': channel.last_delivery_status,
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

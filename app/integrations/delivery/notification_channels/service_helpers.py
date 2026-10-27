from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.integrations.delivery.notification_channels.catalog import domain_label, event_type_label
from app.integrations.delivery.notification_channels.contracts import NotificationMessage
from app.integrations.delivery.notification_channels.lifecycle import NotificationChannelUsage
from app.integrations.delivery.notification_channels.providers import get_notification_provider, provider_labels
from app.models.notification_channel import NotificationChannel, NotificationDelivery


@dataclass(frozen=True, slots=True)
class DeliveryPagination:
    page: int = 1
    per_page: int = 5


_PROVIDER_LABELS = provider_labels()


def _reset_channel_validation(channel: NotificationChannel) -> None:
    channel.test_status = 'not_tested'
    channel.test_message = 'Destination, credentials, or transport configuration changed. Validate the channel again.'
    channel.last_tested_at = None
    channel.last_delivery_status = 'never'
    channel.last_delivery_message = None
    channel.last_delivery_attempt_at = None
    channel.last_delivery_at = None


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


def _provider_label(provider_key: str) -> str:
    return _PROVIDER_LABELS.get(provider_key, provider_key.replace('_', ' ').title())


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

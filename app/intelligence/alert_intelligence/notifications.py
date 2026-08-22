from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app

from app.extensions.db import db
from app.integrations.delivery.notification_channels.contracts import NotificationEvent, NotificationMessage
from app.integrations.delivery.notification_channels.service import dispatch_notification_event
from app.intelligence.alert_intelligence.lifecycle import (
    acknowledgement_suppresses_delivery,
    active_delivery_silence,
)
from app.intelligence.alert_intelligence.routing import (
    FiringRoute,
    firing_routes,
    policy_allows_resolved,
)
from app.intelligence.alert_intelligence.templates import render_case_message
from app.models.alert_ops import AlertCase, AlertCaseEvent
from app.models.notification_channel import NotificationChannel, NotificationDelivery


def dispatch_case_notifications() -> dict[str, int]:
    """Dispatch recommendation-origin firing/repeat/resolved notifications from durable alert cases."""

    stats = {'cases': 0, 'firing': 0, 'resolved': 0, 'failed': 0, 'skipped': 0}
    cases = AlertCase.query.filter_by(source_type='recommendation').order_by(AlertCase.id.asc()).all()
    for case in cases:
        stats['cases'] += 1
        if case.source_state == 'firing' and case.workflow_state != 'closed':
            result = _dispatch_firing(case)
        elif case.source_state == 'resolved' and case.workflow_state == 'closed':
            result = _dispatch_resolved(case)
        else:
            continue
        stats['firing'] += result['firing']
        stats['resolved'] += result['resolved']
        stats['failed'] += result['failed']
        stats['skipped'] += result['skipped']
    return stats


def case_delivery_rows(case: AlertCase, *, limit: int = 20) -> list[dict[str, Any]]:
    prefix = f'alert-case:{case.public_id}:'
    rows = (
        NotificationDelivery.query.filter(NotificationDelivery.event_key.like(f'{prefix}%'))
        .order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())
        .limit(max(limit, 1))
        .all()
    )
    return [
        {
            'id': row.id,
            'event_type': row.event_type,
            'event_label': 'Resolved' if row.event_type == 'alert_ops.resolved' else 'Firing',
            'channel': row.channel.name,
            'provider': row.channel.provider_key.replace('_', ' ').title(),
            'status': (
                'suppressed'
                if row.status == 'skipped' and (row.payload_json or {}).get('delivery_state') == 'suppressed'
                else row.status
            ),
            'attempt_count': row.attempt_count,
            'error': row.error_message or '',
            'suppression_reason': (row.payload_json or {}).get('suppression_reason') or '',
            'created_at': row.created_at,
            'sent_at': row.sent_at,
        }
        for row in rows
    ]


def _dispatch_firing(case: AlertCase) -> dict[str, int]:
    stats = {'firing': 0, 'resolved': 0, 'failed': 0, 'skipped': 0}
    now = datetime.now(UTC)
    if active_delivery_silence(case, now=now) is not None:
        stats['skipped'] += 1
        return stats
    routes = firing_routes(case)
    if not routes:
        stats['skipped'] += 1
        return stats

    escalation_due = _severity_escalation_due(case)
    if acknowledgement_suppresses_delivery(case, now=now) and not escalation_due:
        stats['skipped'] += 1
        return stats

    successful = 0
    for route in routes:
        if not escalation_due and not _route_due(case, route=route, now=now):
            stats['skipped'] += 1
            continue
        repeat = max(route.repeat_interval_minutes, 5)
        bucket = int(now.timestamp() // (repeat * 60))
        sequence = f'route-{route.route_key}:{bucket}'
        result = _deliver_case_event(
            case,
            channel_id=route.channel_id,
            event_state='firing',
            sequence=sequence,
            route=route,
        )
        successful += int(result['successful'])
        stats['failed'] += int(result['failed'])
        stats['skipped'] += int(result['skipped'])
    if successful:
        case.last_firing_notified_at = now
        _timeline(case, 'firing_notified', f'Firing notification delivered to {successful} route/channel target(s).')
        db.session.commit()
        stats['firing'] += successful
    return stats


def _route_due(case: AlertCase, *, route: FiringRoute, now: datetime) -> bool:
    prefix = f'alert-case:{case.public_id}:firing:route-{route.route_key}:'
    row = (
        NotificationDelivery.query.filter(
            NotificationDelivery.event_type == 'alert_ops.firing',
            NotificationDelivery.channel_id == route.channel_id,
            NotificationDelivery.status == 'sent',
            NotificationDelivery.event_key.like(f'{prefix}%'),
        )
        .order_by(NotificationDelivery.sent_at.desc(), NotificationDelivery.id.desc())
        .first()
    )
    if row is None:
        return True
    last_sent = row.sent_at or row.created_at
    if last_sent is None:
        return True
    last_sent = _aware(last_sent)
    return now - last_sent >= timedelta(minutes=max(route.repeat_interval_minutes, 5))


def _severity_escalation_due(case: AlertCase) -> bool:
    if not case.severity_changed_at or not case.previous_severity:
        return False
    if _severity_rank(case.severity) <= _severity_rank(case.previous_severity):
        return False
    last = case.last_firing_notified_at
    return last is None or _aware(last) < _aware(case.severity_changed_at)


def _dispatch_resolved(case: AlertCase) -> dict[str, int]:
    stats = {'firing': 0, 'resolved': 0, 'failed': 0, 'skipped': 0}
    if case.last_resolved_notified_at is not None:
        stats['skipped'] += 1
        return stats
    firing_channels = _successful_firing_channels(case)
    if not firing_channels:
        stats['skipped'] += 1
        return stats
    successful = 0
    for channel_id, route_allows_resolved in firing_channels.items():
        if not route_allows_resolved:
            continue
        result = _deliver_case_event(case, channel_id=channel_id, event_state='resolved', sequence='final')
        successful += int(result['successful'])
        stats['failed'] += int(result['failed'])
        stats['skipped'] += int(result['skipped'])
    if successful:
        case.last_resolved_notified_at = datetime.now(UTC)
        _timeline(case, 'resolved_notified', f'Resolved notification delivered to {successful} channel(s).')
        db.session.commit()
        stats['resolved'] += successful
    return stats


def _deliver_case_event(
    case: AlertCase,
    *,
    channel_id: int,
    event_state: str,
    sequence: str,
    route: FiringRoute | None = None,
) -> dict[str, Any]:
    channel = db.session.get(NotificationChannel, channel_id)
    if channel is None:
        return {'successful': 0, 'failed': 0, 'skipped': 1}
    action_tab = 'resolved' if event_state == 'resolved' else 'active'
    base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '').rstrip('/')
    action_path = f'/intelligence/alert-intelligence?tab={action_tab}&case={case.public_id}'
    action_url = f'{base_url}{action_path}' if base_url else action_path
    title, body, content_format = render_case_message(
        case,
        provider_key=channel.provider_key,
        event_state=event_state,
        action_url=action_url,
    )
    event_type = 'alert_ops.resolved' if event_state == 'resolved' else 'alert_ops.firing'
    event = NotificationEvent(
        event_type=event_type,
        domain=case.domain,
        asset_type=case.asset_type,
        asset_key=case.asset_key,
        severity=case.severity,
        event_key=f'alert-case:{case.public_id}:{event_state}:{sequence}',
        message=NotificationMessage(
            title=title,
            body=body,
            severity=case.severity,
            action_url=action_url,
            action_label='Open Incident Record' if event_state == 'resolved' else 'Open Active Alert',
            content_format=content_format,
        ),
        payload={
            'case_id': case.public_id,
            'alert_name': case.alert_name,
            'source_type': case.source_type,
            'source_ref': case.source_ref,
            'rule_key': case.rule_key,
            'source_state': case.source_state,
            'workflow_state': case.workflow_state,
            'event_state': event_state,
            'content_format': content_format,
            'routing_policy_id': route.policy_id if route is not None else None,
            'route_repeat_interval_minutes': route.repeat_interval_minutes if route is not None else None,
            'route_send_resolved': route.send_resolved if route is not None else None,
        },
    )
    suppression_reason = _channel_suppression_reason(channel)
    if suppression_reason:
        return _record_suppressed_delivery(channel=channel, event=event, reason=suppression_reason)
    _clear_previous_suppressed_delivery(channel_id=channel.id, event_key=event.event_key)
    return dispatch_notification_event(channel_ids=[channel_id], event=event)


def _channel_suppression_reason(channel: NotificationChannel) -> str | None:
    if not channel.enabled:
        return 'channel_disabled'
    if not channel.configured:
        return 'channel_not_configured'
    if channel.test_status != 'success':
        return 'channel_not_validated'
    return None


def _record_suppressed_delivery(
    *,
    channel: NotificationChannel,
    event: NotificationEvent,
    reason: str,
) -> dict[str, int]:
    delivery = NotificationDelivery.query.filter_by(channel_id=channel.id, event_key=event.event_key).first()
    if delivery is None:
        delivery = NotificationDelivery()
        delivery.channel_id = channel.id
        delivery.event_key = event.event_key
        delivery.event_type = event.event_type
        delivery.domain = event.domain
        delivery.asset_type = event.asset_type
        delivery.asset_key = str(event.asset_key)
        delivery.severity = str(event.severity or 'info')
        delivery.attempt_count = 0
        db.session.add(delivery)
    if delivery.status != 'sent':
        delivery.status = 'skipped'
        delivery.error_message = f'Delivery suppressed: {reason.replace("_", " ")}.'
        delivery.payload_json = {
            **dict(event.payload or {}),
            'delivery_state': 'suppressed',
            'suppression_reason': reason,
        }
        db.session.commit()
    return {'successful': 0, 'failed': 0, 'skipped': 1}


def _clear_previous_suppressed_delivery(*, channel_id: int, event_key: str) -> None:
    delivery = NotificationDelivery.query.filter_by(channel_id=channel_id, event_key=event_key).first()
    if delivery is None or delivery.status != 'skipped':
        return
    if (delivery.payload_json or {}).get('delivery_state') != 'suppressed':
        return
    db.session.delete(delivery)
    db.session.flush()


def _successful_firing_channels(case: AlertCase) -> dict[int, bool]:
    """Return channels that received firing delivery and whether any firing route requested resolved delivery."""
    rows = (
        NotificationDelivery.query.filter(
            NotificationDelivery.event_type == 'alert_ops.firing',
            NotificationDelivery.status == 'sent',
            NotificationDelivery.event_key.like(f'alert-case:{case.public_id}:firing:%'),
        )
        .order_by(NotificationDelivery.channel_id.asc(), NotificationDelivery.id.desc())
        .all()
    )
    result: dict[int, bool] = {}
    for row in rows:
        payload = dict(row.payload_json or {})
        route_preference = payload.get('route_send_resolved')
        if route_preference is None:
            # Backward compatibility for delivery rows written before per-route evidence existed.
            route_preference = policy_allows_resolved(case, row.channel_id)
        result[row.channel_id] = bool(result.get(row.channel_id, False) or route_preference)
    return result


def _timeline(case: AlertCase, event_type: str, summary: str) -> None:
    row = AlertCaseEvent()
    row.case_id = case.id
    row.event_type = event_type
    row.summary = summary
    row.metadata_json = {}
    db.session.add(row)


def _severity_rank(value: str) -> int:
    return {'unknown': 0, 'info': 1, 'warning': 2, 'critical': 3}.get(str(value or '').lower(), 0)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

from __future__ import annotations

from typing import Any

from flask import current_app

from app.integrations.delivery.notification_channels.contracts import NotificationEvent, NotificationMessage
from app.integrations.delivery.notification_channels.service import (
    dispatch_notification_event,
    list_event_channel_options,
)
from app.models.report import Report

REPORT_NOTIFICATION_EVENT = 'report.generated'


def get_report_notification_channel_options(*, domain: str = 'kubernetes') -> list[dict[str, Any]]:
    return list_event_channel_options(event_type=REPORT_NOTIFICATION_EVENT, domain=domain)


def deliver_generated_report(report: Report, channel_ids: list[int]) -> dict[str, Any]:
    if not channel_ids:
        return {
            'requested': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'duplicate': 0,
            'results': [],
        }

    domain = str(report.report_domain or 'kubernetes').strip().lower() or 'kubernetes'
    base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '').rstrip('/')
    action_url = f'{base_url}/reports/generated/{report.id}' if base_url else f'/reports/generated/{report.id}'
    status_label = str(report.status or 'ready').replace('_', ' ').title()
    message = NotificationMessage(
        title=f'Report Ready · {report.name}',
        body=(
            f'Type: {str(report.report_type or "report").replace("_", " ").title()}\n'
            f'Format: {str(report.output_format or "").upper()}\n'
            f'Status: {status_label}\n'
            'The governed report artifact is ready in KAORI.'
        ),
        severity='info',
        action_url=action_url,
        action_label='Open Report',
    )
    event = NotificationEvent(
        event_type=REPORT_NOTIFICATION_EVENT,
        domain=domain,
        asset_type='report',
        asset_key=str(report.id),
        severity='info',
        event_key=f'report.generated:{report.id}',
        message=message,
        payload={
            'report_id': report.id,
            'report_name': report.name,
            'report_type': report.report_type,
            'output_format': report.output_format,
            'status': report.status,
        },
    )
    return dispatch_notification_event(channel_ids=channel_ids, event=event)

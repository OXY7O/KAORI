from __future__ import annotations

from typing import Any

from flask import current_app

from app.models.report import Report
from app.reports.delivery.base import DeliveryResult, ReportDeliveryChannel
from app.reports.delivery.telegram import TelegramReportDelivery

_CHANNELS: dict[str, ReportDeliveryChannel] = {'telegram': TelegramReportDelivery()}


def get_delivery_channel_catalog() -> list[dict[str, Any]]:
    telegram_ready = bool(
        str(current_app.config.get('REPORT_TELEGRAM_BOT_TOKEN') or '').strip()
        and str(current_app.config.get('REPORT_TELEGRAM_CHAT_ID') or '').strip()
    )
    return [
        {
            'value': 'telegram',
            'label': 'Telegram',
            'description': 'Send a generated report notification and report detail link to the configured Telegram chat.',
            'icon': 'send',
            'status': 'Ready' if telegram_ready else 'Configuration Required',
            'tone': 'normal' if telegram_ready else 'warning',
            'selectable': True,
        },
        {
            'value': 'email',
            'label': 'Email',
            'description': 'Connect an email provider to deliver report notifications and links.',
            'icon': 'mail',
            'status': 'Not Connected',
            'tone': 'unknown',
            'selectable': False,
        },
        {
            'value': 'slack',
            'label': 'Slack',
            'description': 'Connect a Slack workspace and channel for report notifications.',
            'icon': 'messages-square',
            'status': 'Not Connected',
            'tone': 'unknown',
            'selectable': False,
        },
        {
            'value': 'webhook',
            'label': 'Webhook',
            'description': 'Connect a signed webhook endpoint for report delivery events.',
            'icon': 'webhook',
            'status': 'Not Connected',
            'tone': 'unknown',
            'selectable': False,
        },
    ]


def deliver_generated_report(report: Report, channels: list[str]) -> dict[str, Any]:
    results: list[DeliveryResult] = []
    for key in dict.fromkeys(str(item).strip().lower() for item in channels if str(item).strip()):
        channel = _CHANNELS.get(key)
        if channel is None:
            results.append(DeliveryResult(key, 'skipped', 'The selected delivery channel is not registered.'))
            continue
        results.append(channel.deliver(report))

    successful = sum(1 for result in results if result.success)
    failed = sum(1 for result in results if result.status == 'failed')
    skipped = sum(1 for result in results if result.status == 'skipped')
    return {
        'requested': len(results),
        'successful': successful,
        'failed': failed,
        'skipped': skipped,
        'results': [result.to_dict() for result in results],
    }

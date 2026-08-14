from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app

from app.models.report import Report
from app.reports.delivery.base import DeliveryResult


class TelegramReportDelivery:
    key = 'telegram'

    def deliver(self, report: Report) -> DeliveryResult:
        token = str(current_app.config.get('REPORT_TELEGRAM_BOT_TOKEN') or '').strip()
        chat_id = str(current_app.config.get('REPORT_TELEGRAM_CHAT_ID') or '').strip()
        if not token or not chat_id:
            return DeliveryResult(
                channel=self.key,
                status='skipped',
                message='Telegram delivery is selected, but the bot token or chat ID is not configured.',
            )

        base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '').rstrip('/')
        report_url = f'{base_url}/reports/generated/{report.id}' if base_url else f'/reports/generated/{report.id}'
        status_label = str(report.status or 'ready').replace('_', ' ').title()
        text = (
            f'KAORI Generated Report\n'
            f'{report.name}\n'
            f'Type: {report.report_type.replace("_", " ").title()}\n'
            f'Status: {status_label}\n'
            f'Open: {report_url}'
        )
        body = urlencode({'chat_id': chat_id, 'text': text, 'disable_web_page_preview': 'true'}).encode('utf-8')
        request = Request(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST',
        )
        timeout = max(int(current_app.config.get('REPORT_DELIVERY_TIMEOUT_SECONDS', 10)), 1)
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed Telegram API endpoint.
                payload = json.loads(response.read().decode('utf-8'))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            current_app.logger.warning('Telegram report delivery failed.', exc_info=True)
            return DeliveryResult(
                channel=self.key,
                status='failed',
                message='Telegram could not receive the report notification. Review connectivity and credentials, then retry.',
            )

        if not bool(payload.get('ok')):
            return DeliveryResult(
                channel=self.key,
                status='failed',
                message='Telegram rejected the report notification.',
            )
        return DeliveryResult(
            channel=self.key,
            status='success',
            message='Telegram report notification delivered.',
        )

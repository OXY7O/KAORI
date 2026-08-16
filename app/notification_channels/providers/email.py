from __future__ import annotations

import smtplib
import ssl
from collections.abc import Mapping
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid
from typing import Any

from app.notification_channels.contracts import DeliveryResult, NotificationMessage


def send_email_message(
    *,
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int = 10,
) -> DeliveryResult:
    host = str(provider_config.get('smtp_host') or '').strip()
    port = int(provider_config.get('smtp_port') or 587)
    security = str(provider_config.get('smtp_security') or 'starttls').strip().lower()
    sender_email = str(provider_config.get('sender_email') or '').strip()
    sender_name = str(provider_config.get('sender_name') or 'KAORI').strip() or 'KAORI'
    recipients = [address for _, address in getaddresses([destination]) if address]
    username = str(provider_config.get('smtp_username') or '').strip()
    password = str(credentials.get('password') or '')

    email = EmailMessage()
    email['Subject'] = f'[KAORI][{str(message.severity or "info").upper()}] {message.title}'
    email['From'] = f'{sender_name} <{sender_email}>'
    email['To'] = ', '.join(recipients)
    email['Message-ID'] = make_msgid()
    email.set_content(_render_message(message))

    try:
        if security == 'tls':
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                host,
                port,
                timeout=max(int(timeout_seconds), 1),
                context=ssl.create_default_context(),
            )
        else:
            client = smtplib.SMTP(host, port, timeout=max(int(timeout_seconds), 1))
        with client:
            client.ehlo()
            if security == 'starttls':
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            if username:
                client.login(username, password)
            client.send_message(email)
    except (OSError, smtplib.SMTPException, ValueError):
        return DeliveryResult(False, 'SMTP delivery failed. Review server, TLS, credentials, and recipient settings.')
    return DeliveryResult(True, 'Email message delivered.', str(email['Message-ID']))


def _render_message(message: NotificationMessage) -> str:
    lines = [f'KAORI · {str(message.severity or "info").upper()}', message.title, '', message.body]
    if message.action_url:
        lines.extend(['', f'{message.action_label or "Open KAORI"}: {message.action_url}'])
    return '\n'.join(lines).strip()

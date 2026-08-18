from __future__ import annotations

import smtplib
import ssl
from collections.abc import Mapping
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid
from typing import Any

from app.integrations.delivery.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationMessage,
)
from app.integrations.delivery.notification_channels.providers.form_support import credential_map, positive_int
from app.models.notification_channel import NotificationChannel


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


_EMAIL_SECURITY_MODES = {'starttls', 'tls', 'none'}


def parse_form(form: Any, existing: NotificationChannel | None) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    existing_credentials = credential_map(existing)
    username = str(form.get('smtp_username') or '').strip()
    password = str(form.get('smtp_password') or '').strip()
    existing_username = str((existing.provider_config or {}).get('smtp_username') or '') if existing else ''
    clear_password = existing is not None and bool(existing_username) and not username
    credentials = {'password': '' if clear_password else (password or existing_credentials.get('password', ''))}
    provider_config = {
        'smtp_host': str(form.get('smtp_host') or '').strip(),
        'smtp_port': positive_int(form.get('smtp_port'), default=587),
        'smtp_security': str(form.get('smtp_security') or 'starttls').strip().lower(),
        'smtp_username': username,
        'sender_email': str(form.get('sender_email') or '').strip(),
        'sender_name': str(form.get('sender_name') or 'KAORI').strip() or 'KAORI',
    }
    destination = str(form.get('email_recipients') or '').strip()
    return destination, credentials, provider_config, bool(password) or clear_password


def validate_form(data: NotificationChannelFormInput) -> list[str]:
    errors: list[str] = []
    config = data.provider_config
    if not str(config.get('smtp_host') or '').strip():
        errors.append('SMTP host is required.')
    port = positive_int(config.get('smtp_port'), default=0)
    if port < 1 or port > 65535:
        errors.append('SMTP port must be between 1 and 65535.')
    if config.get('smtp_security') not in _EMAIL_SECURITY_MODES:
        errors.append('SMTP security mode must be STARTTLS, TLS, or None.')
    sender_email = str(config.get('sender_email') or '').strip()
    if not _valid_email_address(sender_email):
        errors.append('A valid sender email address is required.')
    recipients = [address for _, address in getaddresses([data.destination]) if address]
    if not recipients or any(not _valid_email_address(address) for address in recipients):
        errors.append('At least one valid recipient email address is required.')
    username = str(config.get('smtp_username') or '').strip()
    password = str(data.credentials.get('password') or '')
    if username and not password:
        errors.append('SMTP password is required when SMTP username is configured.')
    return errors


def form_view(channel: NotificationChannel) -> dict[str, Any]:
    config = dict(channel.provider_config or {})
    return {
        'email_recipients': channel.destination,
        'smtp_host': str(config.get('smtp_host') or ''),
        'smtp_port': int(config.get('smtp_port') or 587),
        'smtp_security': str(config.get('smtp_security') or 'starttls'),
        'smtp_username': str(config.get('smtp_username') or ''),
        'sender_email': str(config.get('sender_email') or ''),
        'sender_name': str(config.get('sender_name') or 'KAORI'),
    }


def _valid_email_address(value: str) -> bool:
    local, separator, domain = value.rpartition('@')
    return bool(local and separator and domain and '.' in domain and ' ' not in value)

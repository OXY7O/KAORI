"""Retry-After behavioral contract (no network or provider secrets)."""
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import pytest

from app.integrations.delivery.notification_channels.retry_after import (
    MAX_RETRY_AFTER_SECONDS,
    parse_retry_after,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ('header', 'expected'),
    [
        ('0', 0),
        ('30', 30),
        ('0.4', 1),
        ('120.001', 121),
        ('90000', MAX_RETRY_AFTER_SECONDS),
        ('999999999', MAX_RETRY_AFTER_SECONDS),
        ('-1', None),
        (' 15', None),
        ('1.1234', None),
        ('oops', None),
        ('', None),
        (None, None),
        ('\r\nX-Token: leaked', None),
        ('1' * 129, None),
    ],
)
def test_retry_after_delta_seconds_is_bounded(header: str | None, expected: int | None) -> None:
    assert parse_retry_after(header) == expected


def test_http_date_honors_deadline_and_caps_extreme_values() -> None:
    now = datetime(2026, 10, 23, 7, 0, tzinfo=UTC)
    assert parse_retry_after(format_datetime(now + timedelta(seconds=42)), now=now) == 42
    assert parse_retry_after(format_datetime(now - timedelta(seconds=1)), now=now) is None
    assert parse_retry_after(format_datetime(now + timedelta(days=3)), now=now) == MAX_RETRY_AFTER_SECONDS


def test_retry_schedule_contract_and_legacy_semantics() -> None:
    model = (ROOT / 'app/models/notification_channel.py').read_text()
    svc = (ROOT / 'app/integrations/delivery/notification_channels/service.py').read_text()
    migration = (ROOT / 'migrations/versions/20261023_notification_retry_after.py').read_text()
    result = (ROOT / 'app/integrations/delivery/notification_channels/contracts.py').read_text()
    for provider in ('slack', 'discord'):
        text = (ROOT / f'app/integrations/delivery/notification_channels/providers/{provider}.py').read_text()
        assert "exc.headers.get('Retry-After')" in text
        assert 'parse_retry_after(' in text
        assert 'exc.read(' not in text
    assert 'retry_after_seconds: int | None = None' in result
    assert 'next_retry_at: Mapped[datetime | None]' in model
    assert 'ix_notification_deliveries_status_next_retry' in model
    assert 'ix_notification_deliveries_status_next_retry' in migration
    assert "down_revision = '20261023_sc_webhook_job_link'" in migration
    assert 'delivery.next_retry_at = None' in svc
    assert 'NotificationDelivery.next_retry_at <= datetime.now(UTC)' in svc
    assert 'if _provider_retry_not_due(delivery):' in svc
    assert 'due.replace(tzinfo=UTC) if due.tzinfo is None else due.astimezone(UTC)' in svc
    assert 'max(notification_delivery_retry_delay_seconds(), delay)' in svc
    assert 'with_for_update(skip_locked=True)' in svc

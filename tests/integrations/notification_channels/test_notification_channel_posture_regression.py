from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.delivery.notification_channels import service


class Query:
    def __init__(self, channels: list[SimpleNamespace]) -> None:
        self.channels = channels

    def order_by(self, *_args: object) -> Query:
        return self

    def all(self) -> list[SimpleNamespace]:
        return self.channels


def channel(
    *, enabled: bool = True, configured: bool = True, test_status: str = 'success', last_delivery_status: str = 'never'
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        enabled=enabled,
        configured=configured,
        test_status=test_status,
        last_delivery_status=last_delivery_status,
        provider_key='telegram',
    )


@pytest.mark.parametrize(
    ('channels', 'label', 'tone'),
    [
        ([], 'Not Configured', 'unknown'),
        ([channel(enabled=False)], 'Disabled', 'unknown'),
        ([channel(enabled=False), channel(enabled=False)], 'Disabled', 'unknown'),
        ([channel(test_status='not_tested')], 'Validation Required', 'warning'),
        ([channel(test_status='failed')], 'Validation Failed', 'warning'),
        ([channel(last_delivery_status='success')], 'Operational', 'normal'),
        ([channel()], 'Ready', 'info'),
        ([channel(last_delivery_status='success'), channel(test_status='failed')], 'Validation Failed', 'warning'),
        ([channel(last_delivery_status='success'), channel(configured=False)], 'Validation Required', 'warning'),
        ([channel(last_delivery_status='success'), channel(last_delivery_status='failed')], 'Degraded', 'warning'),
    ],
)
def test_notification_overview_aggregate_never_masks_unhealthy_channel(
    monkeypatch: pytest.MonkeyPatch, channels: list[SimpleNamespace], label: str, tone: str
) -> None:
    monkeypatch.setattr(
        service,
        'NotificationChannel',
        SimpleNamespace(
            query=Query(channels),
            id=SimpleNamespace(asc=lambda: None),
        ),
    )
    result = service.notification_channel_summary()
    assert (result['label'], result['tone']) == (label, tone)
    assert result['total'] == len(channels)

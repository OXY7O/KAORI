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


@pytest.mark.parametrize(
    ('outcome_rows', 'archived_count', 'expected_total'),
    [
        ([], 0, 0),
        ([('sent', 75), ('failed', 2), ('skipped', 1)], 3, 78),
    ],
)
def test_notification_overview_metrics_uses_committed_state_without_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
    outcome_rows: list[tuple[str, int]],
    archived_count: int,
    expected_total: int,
) -> None:
    class ArchivedQuery:
        def filter_by(self, **criteria: object) -> SimpleNamespace:
            assert criteria == {'lifecycle_state': 'retired'}
            return SimpleNamespace(count=lambda: archived_count)

    class Column:
        def desc(self) -> Column:
            return self

    class Deliveries:
        def __init__(self, records: list[SimpleNamespace]) -> None:
            self.records = records

        def order_by(self, *_args: object) -> Deliveries:
            return self

        def limit(self, count: int) -> Deliveries:
            assert count == 5
            return self

        def all(self) -> list[SimpleNamespace]:
            return self.records

    class Aggregates:
        def group_by(self, *_args: object) -> Aggregates:
            return self

        def all(self) -> list[tuple[str, int]]:
            return outcome_rows

    recent = [
        SimpleNamespace(
            id=19, status='sent', event_type='alert_intelligence.active_alert',
            channel=SimpleNamespace(name='KAORI Telegram'), created_at=None,
        )
    ] if outcome_rows else []
    monkeypatch.setattr(service, 'NotificationChannel', SimpleNamespace(query=ArchivedQuery()))
    monkeypatch.setattr(
        service, 'NotificationDelivery',
        SimpleNamespace(
            status=Column(), id=Column(), created_at=Column(),
            query=Deliveries(recent),
        ),
    )
    monkeypatch.setattr(service, 'db', SimpleNamespace(
        session=SimpleNamespace(query=lambda *_args: Aggregates()),
    ))
    monkeypatch.setattr(service, 'event_type_label', lambda _: 'Active Alert')
    result = service.notification_overview_metrics()
    assert result['archived'] == archived_count
    assert result['delivery_total'] == expected_total
    assert result['outcomes']['sent'] == (75 if outcome_rows else 0)
    assert result['outcomes']['failed'] == (2 if outcome_rows else 0)
    assert result['outcomes']['queued'] == 0
    assert result['outcomes']['skipped'] == (1 if outcome_rows else 0)
    assert len(result['recent']) == len(recent)
    if recent:
        assert result['recent'][0]['channel_name'] == 'KAORI Telegram'
        assert result['recent'][0]['event_label'] == 'Active Alert'
        assert result['recent'][0]['status_label'] == 'Delivered'

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.definitions.loader import load_definition_document
from app.integrations.delivery.notification_channels import catalog, lifecycle, service
from app.integrations.delivery.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationEvent,
    NotificationMessage,
)
from app.models.notification_channel import NotificationChannel
from app.security.credentials import EncryptedText


def test_channel_policy_event_catalog_preserves_order_and_all_items() -> None:
    definition = load_definition_document(
        'platform_operations/notifications/outbound_delivery.yaml',
        expected_kind='notification_delivery_contract',
    )
    events = definition['events']
    assert isinstance(events, dict)
    expected = [{'value': key, 'label': record['label']} for key, record in events.items()]

    assert catalog.event_type_options() == expected
    assert len(expected) == len({item['value'] for item in expected})
    assert service.event_type_options is catalog.event_type_options

    modal = (
        Path(__file__).resolve().parents[3]
        / 'app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html'
    ).read_text(encoding='utf-8')
    assert '{% for option in payload.event_type_options %}' in modal
    assert 'name="event_types"' in modal
    assert 'value="{{ option.value }}"' in modal


class SessionStub:
    def __init__(self, *, channel: object | None = None) -> None:
        self.channel = channel
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    def delete(self, value: object) -> None:
        self.deleted.append(value)

    def commit(self) -> None:
        self.commits += 1

    def flush(self) -> None:
        self.flushes += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def get(self, _model: object, _identifier: int, **_kwargs: object) -> object | None:
        return self.channel


class ChannelStub:
    def __init__(self) -> None:
        self.id = 7
        self.name = ''
        self.provider_key = ''
        self.enabled = False
        self.lifecycle_state = 'active'
        self.credential_payload: str | None = None
        self.destination: str | None = None
        self.provider_config: dict[str, object] = {}
        self.minimum_severity = 'warning'
        self.domains: list[str] = []
        self.event_types: list[str] = []
        self.test_status = 'success'
        self.test_message: str | None = 'Validated'
        self.last_tested_at: object | None = object()
        self.last_delivery_status = 'success'
        self.last_delivery_message: str | None = 'Delivered'
        self.last_delivery_attempt_at: object | None = object()
        self.last_delivery_at: object | None = object()
        self.created_by_user_id: int | None = None
        self.updated_by_user_id: int | None = None

    @property
    def configured(self) -> bool:
        return bool(self.credential_payload and self.destination)


class DeliveryQueryStub:
    def __init__(self, result: object | None) -> None:
        self.result = result

    def filter_by(self, **_kwargs: object) -> DeliveryQueryStub:
        return self

    def with_for_update(self, **_kwargs: object) -> DeliveryQueryStub:
        return self

    def first(self) -> object | None:
        return self.result


class DeliveryStub:
    query = DeliveryQueryStub(None)

    def __init__(self) -> None:
        self.channel_id = 0
        self.event_key = ''
        self.event_type = ''
        self.domain = ''
        self.asset_type = ''
        self.asset_key = ''
        self.severity = ''
        self.status = 'queued'
        self.payload_json: dict[str, object] = {}
        self.provider_message_id: str | None = None
        self.attempt_count = 0
        self.error_message: str | None = None
        self.sent_at: object | None = None


def _form_input(
    *,
    destination: str = 'ops@example.invalid',
    credentials: dict[str, str] | None = None,
    credential_changed: bool = True,
) -> NotificationChannelFormInput:
    return NotificationChannelFormInput(
        name='Primary Operations',
        provider_key='email',
        enabled=True,
        destination=destination,
        credentials=credentials or {'smtp_password': 'secret-value'},
        provider_config={'smtp_host': 'smtp.example.invalid'},
        minimum_severity='warning',
        domains=('kubernetes',),
        event_types=('report.generated',),
        credential_changed=credential_changed,
    )


def _delivery_event() -> NotificationEvent:
    return NotificationEvent(
        event_type='report.generated',
        domain='kubernetes',
        asset_type='report',
        asset_key='report-41',
        severity='warning',
        event_key='report.generated:41',
        message=NotificationMessage(
            title='Report generated',
            body='The report is ready.',
            severity='warning',
        ),
        payload={'report_id': 41},
    )


def _validated_channel() -> ChannelStub:
    channel = ChannelStub()
    channel.name = 'Primary Operations'
    channel.provider_key = 'email'
    channel.enabled = True
    channel.credential_payload = '{"smtp_password":"secret-value"}'
    channel.destination = 'ops@example.invalid'
    channel.provider_config = {'smtp_host': 'smtp.example.invalid'}
    channel.minimum_severity = 'warning'
    channel.domains = ['kubernetes']
    channel.event_types = ['report.generated']
    return channel


def test_channel_action_return_query_preserves_bounded_registry_state() -> None:
    from flask import Flask

    from app.integrations.delivery.notification_channels.routes import _channel_return_query

    application = Flask(__name__)
    with application.test_request_context(
        '/integrations/notification-channels/1/test',
        method='POST',
        data={
            'channel_page': '3',
            'channel_per_page': '25',
            'channel_search': 'Telegram Operations',
            'channel_provider': 'telegram',
            'channel_state': 'enabled',
        },
    ):
        assert _channel_return_query() == {
            'channel_page': 3,
            'channel_per_page': 25,
            'channel_search': 'Telegram Operations',
            'channel_provider': 'telegram',
            'channel_state': 'enabled',
        }

    with application.test_request_context(
        '/integrations/notification-channels/1/delete',
        method='POST',
        data={'channel_page': '-8', 'channel_per_page': '999999', 'channel_search': 'X' * 500},
    ):
        assert _channel_return_query() == {
            'channel_per_page': 1000,
            'channel_search': 'X' * 128,
        }


def test_notification_channel_create_commits_policy_and_uses_encrypted_model_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub()
    monkeypatch.setattr(service, 'NotificationChannel', ChannelStub)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=session))

    channel = service.create_channel(_form_input(), user_id=23)

    assert channel.name == 'Primary Operations'
    assert channel.provider_key == 'email'
    assert channel.domains == ['kubernetes']
    assert channel.event_types == ['report.generated']
    assert channel.credential_payload == '{"smtp_password":"secret-value"}'
    assert channel.created_by_user_id == 23
    assert channel.updated_by_user_id == 23
    assert channel.test_status == 'not_tested'
    assert session.added == [channel]
    assert session.commits == 1
    assert isinstance(NotificationChannel.__table__.c.credential_payload.type, EncryptedText)


def test_notification_channel_transport_change_resets_validation_but_preserves_unchanged_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub()
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=session))
    channel = _validated_channel()
    original_credential = channel.credential_payload

    service.update_channel(  # type: ignore[arg-type]
        channel,
        _form_input(
            destination='new-ops@example.invalid',
            credentials={},
            credential_changed=False,
        ),
        user_id=24,
    )

    assert channel.destination == 'new-ops@example.invalid'
    assert channel.credential_payload == original_credential
    assert channel.updated_by_user_id == 24
    assert channel.test_status == 'not_tested'
    assert (
        channel.test_message
        == 'Destination, credentials, or transport configuration changed. Validate the channel again.'
    )
    assert channel.last_tested_at is None
    assert channel.last_delivery_status == 'never'
    assert channel.last_delivery_message is None
    assert channel.last_delivery_attempt_at is None
    assert channel.last_delivery_at is None
    assert session.commits == 1


def test_notification_channel_delete_guard_preserves_auditable_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub()
    channel = _validated_channel()
    usage = lifecycle.NotificationChannelUsage(
        delivery_records=2,
        report_schedules=1,
        report_schedule_names=('Daily Operations',),
    )
    monkeypatch.setattr(lifecycle, 'get_channel_usage', lambda _channel_id: usage)
    monkeypatch.setattr(lifecycle, 'db', SimpleNamespace(session=session))

    with pytest.raises(lifecycle.NotificationChannelDeletionBlocked) as exc_info:
        lifecycle.delete_channel(channel)  # type: ignore[arg-type]

    assert exc_info.value.usage == usage
    assert 'delivery evidence record(s)' in str(exc_info.value)
    assert 'report schedule(s)' in str(exc_info.value)
    assert session.deleted == []
    assert session.commits == 0


def test_retire_channel_preserves_history_and_blocks_schedules(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = _validated_channel()
    channel.lifecycle_state = 'active'
    session = SessionStub(channel=channel)
    monkeypatch.setattr(lifecycle, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(
        lifecycle,
        'get_channel_usage',
        lambda _id: lifecycle.NotificationChannelUsage(
            delivery_records=26,
            report_schedules=0,
            report_schedule_names=(),
        ),
    )
    lifecycle.retire_channel(channel, reason='Destination replaced with managed operations bot', user_id=19)  # type: ignore[arg-type]
    assert channel.lifecycle_state == 'retired'
    assert channel.enabled is False
    assert channel.retirement_reason == 'Destination replaced with managed operations bot'
    assert channel.retired_by_user_id == 19
    assert channel.retired_at is not None
    assert session.deleted == []
    assert session.commits == 1

    with pytest.raises(lifecycle.NotificationChannelRetirementBlocked):
        lifecycle.retire_channel(channel, reason='Repeat retirement is forbidden', user_id=19)  # type: ignore[arg-type]
    assert session.commits == 1

    channel.lifecycle_state = 'active'
    monkeypatch.setattr(
        lifecycle,
        'get_channel_usage',
        lambda _id: lifecycle.NotificationChannelUsage(
            delivery_records=26,
            report_schedules=1,
            report_schedule_names=('Weekly Ops',),
        ),
    )
    with pytest.raises(lifecycle.NotificationChannelRetirementBlocked):
        lifecycle.retire_channel(channel, reason='Destination replaced', user_id=19)  # type: ignore[arg-type]
    assert session.commits == 1


def test_retired_channel_is_never_eligible_or_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = _validated_channel()
    channel.lifecycle_state = 'retired'
    channel.enabled = True  # Fail-safe even if inconsistent legacy data exists.
    sent = []
    monkeypatch.setattr(service, 'get_notification_provider', lambda _key: sent.append('adapter'))
    assert (
        service._channel_matches_event(
            channel,
            domain='kubernetes',
            event_type='alert_intelligence.active_alert',
            severity='warning',
        )
        is False
    )
    result = service._deliver(channel, NotificationMessage(title='No send', body='Retired', severity='warning'))
    assert result.success is False
    assert sent == []
    assert service.test_channel(channel).success is False
    assert (
        service.send_channel_preview_message(
            channel,
            NotificationMessage(title='No preview', body='Retired', severity='warning'),
        ).success
        is False
    )


def test_disabled_channel_still_cannot_delete_committed_delivery_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _validated_channel()
    channel.enabled = False
    session = SessionStub()
    usage = lifecycle.NotificationChannelUsage(
        delivery_records=26,
        report_schedules=0,
        report_schedule_names=(),
    )
    monkeypatch.setattr(lifecycle, 'get_channel_usage', lambda _channel_id: usage)
    monkeypatch.setattr(lifecycle, 'db', SimpleNamespace(session=session))

    with pytest.raises(lifecycle.NotificationChannelDeletionBlocked) as exc_info:
        lifecycle.delete_channel(channel)  # type: ignore[arg-type]

    assert exc_info.value.usage.delivery_records == 26
    assert exc_info.value.usage.report_schedules == 0
    assert session.deleted == []
    assert session.commits == 0


def test_notification_channel_delete_commits_when_no_dependency_remains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub()
    channel = _validated_channel()
    usage = lifecycle.NotificationChannelUsage(
        delivery_records=0,
        report_schedules=0,
        report_schedule_names=(),
    )
    monkeypatch.setattr(lifecycle, 'get_channel_usage', lambda _channel_id: usage)
    monkeypatch.setattr(lifecycle, 'db', SimpleNamespace(session=session))

    lifecycle.delete_channel(channel)  # type: ignore[arg-type]

    assert session.deleted == [channel]
    assert session.commits == 1


def test_notification_delivery_failure_is_persisted_as_retryable_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _validated_channel()
    session = SessionStub(channel=channel)
    DeliveryStub.query = DeliveryQueryStub(None)
    monkeypatch.setattr(service, 'NotificationDelivery', DeliveryStub)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(service, 'event_severity_scoped', lambda _event_type: True)
    monkeypatch.setattr(service, 'notification_delivery_max_attempts', lambda: 3)

    def provider_send(_channel: object, _message: object) -> DeliveryResult:
        assert session.commits == 1, 'Queued intent must commit before provider side effect'
        return DeliveryResult(False, 'provider unavailable')

    monkeypatch.setattr(service, '_deliver', provider_send)
    monkeypatch.setattr(service, 'encrypt_credential', lambda _payload: 'enc:v1:test')

    stats = service.dispatch_notification_event(channel_ids=[7], event=_delivery_event())

    assert stats['requested'] == 1
    assert stats['successful'] == 0
    assert stats['failed'] == 1
    assert stats['duplicate'] == 0
    assert len(session.added) == 1
    delivery = session.added[0]
    assert isinstance(delivery, DeliveryStub)
    assert delivery.event_key == 'report.generated:41'
    assert delivery.event_type == 'report.generated'
    assert delivery.status == 'failed'
    assert delivery.attempt_count == 1
    assert delivery.error_message == 'provider unavailable'
    assert channel.last_delivery_status == 'failed'
    assert channel.last_delivery_message == 'provider unavailable'
    assert session.flushes == 1
    assert session.commits == 2  # Queued intent before sending, outcome afterward.


def test_notification_delivery_deduplicates_already_sent_event_without_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _validated_channel()
    session = SessionStub(channel=channel)
    existing_delivery = SimpleNamespace(status='sent', attempt_count=1)
    DeliveryStub.query = DeliveryQueryStub(existing_delivery)
    provider_calls: list[tuple[object, object]] = []
    monkeypatch.setattr(service, 'NotificationDelivery', DeliveryStub)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(service, 'event_severity_scoped', lambda _event_type: True)
    monkeypatch.setattr(service, 'notification_delivery_max_attempts', lambda: 3)

    def deliver(channel_arg: object, message_arg: object) -> DeliveryResult:
        provider_calls.append((channel_arg, message_arg))
        return DeliveryResult(True, 'sent')

    monkeypatch.setattr(service, '_deliver', deliver)

    stats = service.dispatch_notification_event(channel_ids=[7], event=_delivery_event())

    assert stats['requested'] == 1
    assert stats['duplicate'] == 1
    assert stats['skipped'] == 1
    assert stats['successful'] == 0
    assert stats['failed'] == 0
    assert provider_calls == []
    assert session.added == []
    assert session.commits == 0

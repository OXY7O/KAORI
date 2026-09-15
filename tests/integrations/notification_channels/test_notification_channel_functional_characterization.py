from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.delivery.notification_channels import lifecycle, service
from app.integrations.delivery.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationEvent,
    NotificationMessage,
)
from app.models.notification_channel import NotificationChannel
from app.security.credentials import EncryptedText


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

    def get(self, _model: object, _identifier: int) -> object | None:
        return self.channel


class ChannelStub:
    def __init__(self) -> None:
        self.id = 7
        self.name = ''
        self.provider_key = ''
        self.enabled = False
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
    assert channel.test_message == 'Destination, credentials, or transport configuration changed. Validate the channel again.'
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
    monkeypatch.setattr(service, '_deliver', lambda _channel, _message: DeliveryResult(False, 'provider unavailable'))

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
    assert session.commits == 1


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

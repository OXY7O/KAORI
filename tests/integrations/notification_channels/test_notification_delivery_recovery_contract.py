from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.delivery.notification_channels import config, service
from app.integrations.delivery.notification_channels.contracts import NotificationMessage


def channel() -> SimpleNamespace:
    return SimpleNamespace(
        provider_key='telegram', destination='channel-A', provider_config={},
        credential_payload='{"bot_token":"secret"}',
        last_delivery_status='never', last_delivery_at=None,
        last_delivery_message=None, last_delivery_attempt_at=None,
    )


def message() -> NotificationMessage:
    return NotificationMessage(
        title='Report Ready', body='Committed evidence', severity='info',
        action_url='/reports/generated/41', action_label='Open Report',
    )


def test_encrypted_replay_snapshot_and_transport_change_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, 'encrypt_credential', lambda raw: 'enc:v1:' + raw)
    monkeypatch.setattr(service, 'decrypt_credential', lambda raw: raw.removeprefix('enc:v1:'))
    target = channel()
    replay = service._transport_snapshot(target, message())
    assert replay.startswith('enc:v1:')
    delivery = SimpleNamespace(payload_json={service._REPLAY_KEY: replay})
    assert service._replay_message(delivery, target) == message()
    target.destination = 'channel-B'
    assert service._replay_message(delivery, target) is None
    assert service._replay_message(SimpleNamespace(payload_json={}), target) is None


def test_queued_intent_is_committed_before_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    commits: list[tuple[str, int]] = []
    row = SimpleNamespace(payload_json={'report_id': 41}, attempt_count=0,
                          status='queued', error_message=None, updated_at=None)
    monkeypatch.setattr(service, 'db', SimpleNamespace(
        session=SimpleNamespace(commit=lambda: commits.append((row.status, row.attempt_count)))
    ))
    monkeypatch.setattr(service, '_transport_snapshot', lambda *_: 'enc:v1:replay')
    service._begin_delivery_attempt(row, channel(), message())
    assert commits == [('queued', 1)]
    assert row.payload_json[service._REPLAY_KEY] == 'enc:v1:replay'


def test_delivery_outcome_is_separate_durable_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    commits: list[str] = []
    row = SimpleNamespace(status='queued', error_message=None, sent_at=None,
                          provider_message_id=None, updated_at=None)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=SimpleNamespace(
        commit=lambda: commits.append(row.status)
    )))
    service._record_delivery_outcome(row, channel(), service.DeliveryResult(False, 'provider down'))
    assert commits == ['failed']
    assert row.error_message == 'provider down'


def test_recovery_schedule_opt_in_and_independent_of_intelligence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ALERT_INTELLIGENCE_NOTIFICATION_ENABLED', 'false')
    monkeypatch.delenv('NOTIFICATION_DELIVERY_RECOVERY_ENABLED', raising=False)
    assert config.build_notification_beat_schedule() == {}
    monkeypatch.setenv('NOTIFICATION_DELIVERY_RECOVERY_ENABLED', 'true')
    schedule = config.build_notification_beat_schedule()
    assert 'notification-channel-delivery-recovery' in schedule
    assert 'alert-intelligence-notification-dispatch' not in schedule


def test_retry_stale_threshold_exceeds_transport_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('NOTIFICATION_DELIVERY_RETRY_DELAY_SECONDS', '1')
    monkeypatch.setenv('NOTIFICATION_DELIVERY_TIMEOUT_SECONDS', '60')
    assert config.notification_delivery_retry_delay_seconds() >= 120
    assert config.notification_delivery_timeout_seconds() == 60

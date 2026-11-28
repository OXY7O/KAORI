from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select

from app.integrations.delivery.notification_channels import config, service
from app.integrations.delivery.notification_channels.contracts import NotificationMessage


def channel() -> SimpleNamespace:
    return SimpleNamespace(
        provider_key='telegram',
        lifecycle_state='active',
        destination='channel-A',
        provider_config={},
        credential_payload='{"bot_token":"secret"}',
        last_delivery_status='never',
        last_delivery_at=None,
        last_delivery_message=None,
        last_delivery_attempt_at=None,
    )


def message() -> NotificationMessage:
    return NotificationMessage(
        title='Report Ready',
        body='Committed evidence',
        severity='info',
        action_url='/reports/generated/41',
        action_label='Open Report',
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
    row = SimpleNamespace(
        payload_json={'report_id': 41}, attempt_count=0, status='queued', error_message=None, updated_at=None
    )
    monkeypatch.setattr(
        service,
        'db',
        SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append((row.status, row.attempt_count)))),
    )
    monkeypatch.setattr(service, '_transport_snapshot', lambda *_: 'enc:v1:replay')
    service._begin_delivery_attempt(row, channel(), message())
    assert commits == [('queued', 1)]
    assert row.payload_json[service._REPLAY_KEY] == 'enc:v1:replay'


def test_delivery_outcome_is_separate_durable_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    commits: list[str] = []
    row = SimpleNamespace(status='queued', error_message=None, sent_at=None, provider_message_id=None, updated_at=None)
    monkeypatch.setattr(
        service, 'db', SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append(row.status)))
    )
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


@pytest.mark.parametrize('domain', ['kubernetes', 'secrets_pki'])
def test_due_recovery_claims_a_row_before_replaying(monkeypatch: pytest.MonkeyPatch, domain: str) -> None:
    calls: list[str] = []
    item = SimpleNamespace(
        attempt_count=1,
        status='failed',
        channel=channel(),
        domain=domain,
        event_type='report.generated' if domain == 'kubernetes' else 'alert_ops.firing',
        severity='info',
        updated_at=None,
    )

    class Column:
        def __le__(self, _value: object) -> Column:
            return self

        def __lt__(self, _value: object) -> Column:
            return self

        def is_(self, _value: object) -> Column:
            return self

        def __eq__(self, _value: object) -> Column:  # type: ignore[override]
            return self

        def in_(self, _value: object) -> Column:
            return self

        def asc(self) -> Column:
            return self

    class Query:
        def filter(self, *_args: object) -> Query:
            return self

        def order_by(self, *_args: object) -> Query:
            return self

        def with_for_update(self, *, skip_locked: bool) -> Query:
            assert skip_locked is True
            calls.append('locked')
            return self

        def first(self) -> SimpleNamespace | None:
            return item if calls.count('locked') == 1 else None

    columns = SimpleNamespace(
        query=Query(),
        status=Column(),
        updated_at=Column(),
        next_retry_at=Column(),
        attempt_count=Column(),
        id=Column(),
    )
    monkeypatch.setattr(service, 'NotificationDelivery', columns)
    monkeypatch.setattr(service, '_generic_recovery_eligible', lambda: True)
    monkeypatch.setattr(service, 'or_', lambda *_: True)
    monkeypatch.setattr(service, '_replay_message', lambda *_: message())
    monkeypatch.setattr(service, '_channel_matches_event', lambda *_, **__: True)

    def claim(*_: object) -> None:
        calls.append('committed-claim')
        item.attempt_count += 1

    def send(*_: object) -> service.DeliveryResult:
        assert calls.index('committed-claim') < len(calls)
        calls.append('provider')
        return service.DeliveryResult(True, 'accepted')

    monkeypatch.setattr(service, '_begin_delivery_attempt', claim)
    monkeypatch.setattr(service, '_deliver', send)
    monkeypatch.setattr(service, '_record_delivery_outcome', lambda *_: calls.append('result-commit'))
    if domain == 'secrets_pki':
        monkeypatch.setattr(
            service, 'db', SimpleNamespace(session=SimpleNamespace(commit=lambda: calls.append('blocked')))
        )
    result = service.recover_notification_deliveries(limit=1)
    if domain == 'secrets_pki':
        assert result == {'claimed': 0, 'sent': 0, 'failed': 0, 'skipped': 1}
        assert item.status == 'skipped'
        assert calls == ['locked', 'blocked']
    else:
        assert result == {'claimed': 1, 'sent': 1, 'failed': 0, 'skipped': 0}
        assert calls == ['locked', 'committed-claim', 'provider', 'result-commit']


def test_generic_recovery_excludes_only_manual_scoped_vault_journal() -> None:
    table = service.NotificationDelivery.__table__
    engine = create_engine('sqlite://')
    try:
        with engine.begin() as connection:
            table.create(connection)
            common = {
                'channel_id': 1,
                'event_type': 'alert_ops.firing',
                'asset_type': 'vault_instance',
                'asset_key': '42',
                'domain': 'secrets_pki',
                'severity': 'warning',
                'status': 'failed',
                'payload_json': {},
                'attempt_count': 1,
            }
            connection.execute(
                table.insert(),
                [
                    {**common, 'event_key': 'alert-case:CA-1:firing:scoped-v1'},
                    {**common, 'event_key': 'alert-case:CA-2:firing'},
                    {**common, 'event_key': 'alert-case:CA-3:firing:scoped-v1', 'domain': 'kubernetes'},
                ],
            )
            eligible = connection.execute(
                select(table.c.event_key).where(service._generic_recovery_eligible())
            ).scalars().all()
            assert set(eligible) == {'alert-case:CA-2:firing', 'alert-case:CA-3:firing:scoped-v1'}
    finally:
        engine.dispose()

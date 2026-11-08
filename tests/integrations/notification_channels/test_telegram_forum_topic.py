from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs

import pytest
from werkzeug.datastructures import MultiDict

from app.integrations.delivery.notification_channels import service
from app.integrations.delivery.notification_channels.contracts import (
    NotificationChannelFormInput,
    NotificationMessage,
)
from app.integrations.delivery.notification_channels.providers import _send_telegram, telegram


def _input(topic_id: object | None) -> NotificationChannelFormInput:
    return NotificationChannelFormInput(
        name='KAORI Alert',
        provider_key='telegram',
        enabled=True,
        destination='-1001234567890',
        credentials={'bot_token': 'dummy-token'},
        provider_config=({'message_thread_id': topic_id} if topic_id is not None else {}),
        minimum_severity='warning',
        domains=('kubernetes',),
        event_types=('alert_ops.firing',),
        credential_changed=False,
    )


def _message() -> NotificationMessage:
    return NotificationMessage(title='Alert', body='Test evidence', severity='warning')


@pytest.mark.parametrize('raw', ('abc', '0', '-7', '1.5', '2147483648', '５'))
def test_invalid_telegram_topic_id_is_rejected(raw: str) -> None:
    parsed = telegram.parse_form(
        MultiDict({'target_chat_id': '-1001234567890', 'telegram_topic_id': raw, 'bot_token': 'dummy'}),
        None,
    )
    data = _input(parsed[2].get('message_thread_id'))
    assert 'Telegram Topic ID must be a positive integer (1–2147483647).' in telegram.validate_form(data)


@pytest.mark.parametrize('raw,expected', [('123', 123), (' 0042 ', 42), ('2147483647', 2147483647)])
def test_valid_topic_is_normalized_and_exposed_for_edit(raw: str, expected: int) -> None:
    parsed = telegram.parse_form(
        MultiDict(
            {
                'target_chat_id': '-1001234567890',
                'telegram_topic_id': raw,
                'bot_token': 'dummy',
            }
        ),
        None,
    )
    assert parsed[2] == {'message_thread_id': expected}
    assert telegram.validate_form(_input(expected)) == []
    channel = SimpleNamespace(destination='-1001234567890', provider_config=parsed[2])
    assert telegram.form_view(channel)['telegram_topic_id'] == str(expected)


def test_blank_topic_preserves_legacy_chat_only_delivery() -> None:
    parsed = telegram.parse_form(
        MultiDict(
            {
                'target_chat_id': '-1001234567890',
                'telegram_topic_id': '',
                'bot_token': 'dummy',
            }
        ),
        None,
    )
    assert parsed[2] == {}
    assert telegram.validate_form(_input(None)) == []


class _Response:
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"ok":true,"result":{"message_id":111}}'


@pytest.mark.parametrize('topic_id', [None, 123])
def test_adapter_posts_thread_only_when_configured(
    monkeypatch: pytest.MonkeyPatch,
    topic_id: int | None,
) -> None:
    captured: list[dict[str, list[str]]] = []

    def fake_urlopen(request: object, *, timeout: int) -> _Response:
        assert timeout == 10
        body = getattr(request, 'data')
        assert isinstance(body, bytes)
        captured.append(parse_qs(body.decode('utf-8')))
        return _Response()

    monkeypatch.setattr(telegram, 'urlopen', fake_urlopen)
    result = _send_telegram(
        {'bot_token': 'dummy-token'},
        '-1001234567890',
        {'message_thread_id': topic_id} if topic_id is not None else {},
        _message(),
        10,
    )
    assert result.success
    assert result.provider_message_id == '111'
    assert captured[0]['chat_id'] == ['-1001234567890']
    if topic_id is None:
        assert 'message_thread_id' not in captured[0]
    else:
        assert captured[0]['message_thread_id'] == [str(topic_id)]


def test_channel_test_delivery_targets_configured_forum_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, list[str]]] = []

    def fake_urlopen(request: object, *, timeout: int) -> _Response:
        assert timeout == 10
        data = getattr(request, 'data')
        assert isinstance(data, bytes)
        captured.append(parse_qs(data.decode('utf-8')))
        return _Response()

    monkeypatch.setattr(telegram, 'urlopen', fake_urlopen)
    monkeypatch.setattr(service, 'notification_delivery_timeout_seconds', lambda: 10)
    commits: list[bool] = []
    monkeypatch.setattr(
        service,
        'db',
        SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append(True))),
    )
    channel = SimpleNamespace(
        name='KAORI Alert',
        provider_key='telegram',
        configured=True,
        lifecycle_state='active',
        credential_payload='{"bot_token":"dummy-token"}',
        destination='-1001234567890',
        provider_config={'message_thread_id': 123},
        test_status='not_tested',
        test_message=None,
        last_tested_at=None,
    )

    result = service.test_channel(channel)
    assert result.success
    assert captured[0]['message_thread_id'] == ['123']
    assert 'Notification Channel Test' in captured[0]['text'][0]
    assert channel.test_status == 'success'
    assert commits == [True]


def test_invalid_stored_topic_fails_closed_without_sending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbid_transport(*_args: object, **_kwargs: object) -> object:
        pytest.fail('Invalid topic configuration must never fall back to chat delivery')

    monkeypatch.setattr(telegram, 'urlopen', forbid_transport)
    result = _send_telegram(
        {'bot_token': 'dummy-token'},
        '-1001234567890',
        {'message_thread_id': 'invalid'},
        _message(),
        10,
    )
    assert not result.success
    assert 'invalid' in result.message


@pytest.mark.parametrize('next_topic', [234, None])
def test_changing_or_clearing_topic_invalidates_previous_test(
    monkeypatch: pytest.MonkeyPatch,
    next_topic: int | None,
) -> None:
    channel = SimpleNamespace(
        name='KAORI Alert',
        provider_key='telegram',
        enabled=True,
        lifecycle_state='active',
        credential_payload='{"bot_token":"dummy-token"}',
        destination='-1001234567890',
        provider_config={'message_thread_id': 123},
        minimum_severity='warning',
        domains=['kubernetes'],
        event_types=['alert_ops.firing'],
        test_status='success',
        test_message='Validated',
        last_tested_at=object(),
        last_delivery_status='success',
        last_delivery_message='Sent',
        last_delivery_attempt_at=object(),
        last_delivery_at=object(),
        updated_by_user_id=None,
    )
    commits: list[bool] = []
    monkeypatch.setattr(
        service,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(commit=lambda: commits.append(True)),
        ),
    )
    service.update_channel(channel, _input(next_topic), user_id=9)
    assert channel.provider_config == ({'message_thread_id': next_topic} if next_topic is not None else {})
    assert channel.test_status == 'not_tested'
    assert channel.last_delivery_status == 'never'
    assert channel.last_tested_at is None
    assert channel.credential_payload == '{"bot_token":"dummy-token"}'
    assert commits == [True]

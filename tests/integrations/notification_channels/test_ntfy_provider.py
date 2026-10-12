from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from werkzeug.datastructures import MultiDict

from app.integrations.delivery.notification_channels.contracts import NotificationMessage
from app.integrations.delivery.notification_channels.providers import ntfy


def _form(**overrides: str) -> MultiDict[str, str]:
    return MultiDict({
        'ntfy_base_url': 'https://notify.example.test',
        'ntfy_topic': 'kaori-alerts',
        'ntfy_access_token': 'sample-access-token',
        **overrides,
    })


def _data(form: MultiDict[str, str]) -> object:
    parsed = ntfy.parse_form(form, None)
    return SimpleNamespace(destination=parsed[0], credentials=parsed[1], provider_config=parsed[2])


def _message() -> NotificationMessage:
    return NotificationMessage(title='Disk warning', body='Disk usage above limit', severity='critical')


@pytest.mark.parametrize('origin,ok', [
    ('https://notify.example.test', True),
    ('https://notify.example.test/', True),
    ('https://notify.example.test/path', False),
    ('http://notify.example.test', False),
    ('https://user:pass@notify.example.test', False),
    ('https://notify.example.test/?token=123', False),
    ('https://notify.example.test:bad', False),
    ('https://notify.example.test@127.0.0.1', False),
    ('https://[::1', False),
])
def test_ntfy_origin_normalization(origin: str, ok: bool) -> None:
    assert (ntfy._origin(origin) is not None) == ok


def test_ntfy_denies_unapproved_origin_even_for_explicit_private_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('NOTIFICATION_NTFY_ALLOWED_ORIGINS', raising=False)
    result = ntfy.send_ntfy_message(
        credentials={'access_token': 'token'}, destination='kaori-alerts',
        provider_config={'base_url': 'https://127.0.0.1'}, message=_message(),
    )
    assert not result.success
    assert 'not approved' in result.message


@pytest.mark.parametrize('topic', ['no/slash', 'bad space', '', '../admin', 'x' * 65])
def test_ntfy_topic_validation_rejects_invalid(topic: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('NOTIFICATION_NTFY_ALLOWED_ORIGINS', 'https://notify.example.test')
    assert ntfy.validate_form(_data(_form(ntfy_topic=topic)))


def test_ntfy_token_preservation_and_secret_free_edit() -> None:
    channel = SimpleNamespace(
        destination='kaori-alerts', provider_config={'base_url': 'https://notify.example.test'},
        credential_payload='{"access_token":"saved-token"}',
    )
    fields = ntfy.form_view(channel)
    assert 'saved-token' not in str(fields)
    parsed = ntfy.parse_form(_form(ntfy_access_token=''), channel)
    assert parsed[1]['access_token'] == 'saved-token'
    assert parsed[3] is False


def test_ntfy_publish_with_trusted_ca_bearer_headers_and_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('NOTIFICATION_NTFY_ALLOWED_ORIGINS', 'https://notify.example.test')
    monkeypatch.setenv('NOTIFICATION_NTFY_CA_BUNDLE', '/approved/ca.pem')
    opener = Mock()
    response = Mock()
    response.status = 200
    response.read.return_value = json.dumps({'id': 'msg-007'}).encode()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    opener.open.return_value = response
    handlers: list[object] = []
    def factory(*items: object) -> Mock:
        handlers.extend(items)
        return opener
    context_args: list[object] = []
    def make_context(*, cafile: str | None = None) -> object:
        context_args.append(cafile)
        return object()
    monkeypatch.setattr(ntfy, 'build_opener', factory)
    monkeypatch.setattr(ntfy.ssl, 'create_default_context', make_context)
    result = ntfy.send_ntfy_message(
        credentials={'access_token': 'test-token'}, destination='kaori-alerts',
        provider_config={'base_url': 'https://notify.example.test'}, message=_message(),
    )
    assert result.success and result.provider_message_id == 'msg-007'
    assert context_args == ['/approved/ca.pem']
    assert any(isinstance(item, ntfy.DenyRedirects) for item in handlers)
    req = opener.open.call_args.args[0]
    assert req.full_url == 'https://notify.example.test/kaori-alerts'
    assert req.get_header('Authorization') == 'Bearer test-token'
    assert req.get_header('X-priority') == '5'


def test_ntfy_refuses_redirect_without_disclosing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('NOTIFICATION_NTFY_ALLOWED_ORIGINS', 'https://notify.example.test')
    opener = Mock()
    opener.open.side_effect = HTTPError(
        'https://notify.example.test/kaori-alerts', 302, 'Redirect', {}, None,
    )
    monkeypatch.setattr(ntfy, 'build_opener', lambda *_args: opener)
    result = ntfy.send_ntfy_message(
        credentials={'access_token': 'secret'}, destination='kaori-alerts',
        provider_config={'base_url': 'https://notify.example.test'}, message=_message(),
    )
    assert not result.success and 'HTTP 302' in result.message
    assert 'secret' not in result.message
    assert ntfy.DenyRedirects().redirect_request(
        Request('https://notify.example.test'), None, 302, 'Redirect', {}, 'http://127.0.0.1/',
    ) is None

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from werkzeug.datastructures import MultiDict

from app.integrations.delivery.notification_channels.contracts import NotificationMessage
from app.integrations.delivery.notification_channels.providers import discord

URL = 'https://discord.com/api/webhooks/123456789012345678/Example-token_123'


def _message() -> NotificationMessage:
    return NotificationMessage(
        title='Critical alert', body='Do not ping @everyone or <@123456789012345678>',
        severity='critical',
    )


@pytest.mark.parametrize('url,valid', [
    (URL, True),
    ('https://discord.com/api/v10/webhooks/123456789012345678/Example-token_123', True),
    ('http://discord.com/api/webhooks/123456789012345678/Example-token_123', False),
    ('https://evil.example/api/webhooks/123456789012345678/Example-token_123', False),
    ('https://discord.com:444/api/webhooks/123456789012345678/Example-token_123', False),
    ('https://x:password@discord.com/api/webhooks/123456789012345678/Example-token_123', False),
    (URL + '?wait=true', False),
    ('https://[broken', False),
])
def test_discord_webhook_origin_and_path_validation(url: str, valid: bool) -> None:
    assert discord._valid_webhook_url(url) is valid


def test_discord_parser_keeps_webhook_secret_out_of_edit_view() -> None:
    old = SimpleNamespace(destination='ops', credential_payload='{"webhook_url":"' + URL + '"}')
    parsed = discord.parse_form(MultiDict({
        'discord_destination': 'KAORI / Alerts', 'discord_webhook_url': '',
    }), old)
    assert parsed[1] == {'webhook_url': URL}
    assert parsed[3] is False
    assert discord.form_view(old) == {'discord_destination': 'ops'}


def test_discord_204_success_sends_mentions_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = Mock()
    response = MagicMock()
    response.status = 204
    opener.open.return_value = response
    handlers = []
    def factory(*args: object) -> Mock:
        handlers.extend(args)
        return opener
    monkeypatch.setattr(discord, 'build_opener', factory)
    result = discord.send_discord_message(
        credentials={'webhook_url': URL}, destination='KAORI / Alerts',
        provider_config={}, message=_message(),
    )
    assert result.success
    request = opener.open.call_args.args[0]
    payload = json.loads(request.data)
    assert payload['allowed_mentions'] == {'parse': []}
    assert '@everyone' in payload['content']
    assert any(isinstance(x, discord.DenyRedirects) for x in handlers)


def test_discord_200_with_message_id(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = Mock()
    response = MagicMock()
    response.status = 200
    response.read.return_value = b'{"id":"111"}'
    opener.open.return_value = response
    monkeypatch.setattr(discord, 'build_opener', lambda *_items: opener)
    result = discord.send_discord_message(
        credentials={'webhook_url': URL}, destination='ops',
        provider_config={}, message=_message(),
    )
    assert result.success and result.provider_message_id == '111'


def test_discord_rate_limit_and_redirect_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = Mock()
    opener.open.side_effect = HTTPError(URL, 429, 'Too many requests', {}, None)
    monkeypatch.setattr(discord, 'build_opener', lambda *_items: opener)
    result = discord.send_discord_message(
        credentials={'webhook_url': URL}, destination='ops',
        provider_config={}, message=_message(),
    )
    assert not result.success and '429' in result.message and 'Example-token_123' not in result.message
    assert discord.DenyRedirects().redirect_request(
        Request(URL), None, 302, 'Found', {}, 'http://127.0.0.1/',
    ) is None


def test_discord_malformed_secret_rejected() -> None:
    data = SimpleNamespace(destination='ops', credentials={'webhook_url': 'https://evil.invalid'})
    assert discord.validate_form(data)

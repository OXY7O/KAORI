from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from werkzeug.datastructures import MultiDict

from app.integrations.delivery.notification_channels.contracts import NotificationMessage
from app.integrations.delivery.notification_channels.providers import slack

WEBHOOK = 'https://hooks.slack.com/services/T123/B456/token789'


def _message() -> NotificationMessage:
    return NotificationMessage(title='Alert', body='Unsafe <!here> & <@U123>', severity='critical')


@pytest.mark.parametrize('url,approved', [
    (WEBHOOK, True),
    ('https://hooks.slack-gov.com/services/T123/B456/token789', True),
    ('https://evil.example/services/T123/B456/token789', False),
    ('http://hooks.slack.com/services/T123/B456/token789', False),
    ('https://hooks.slack.com/services/T123/B456/token789?x=1', False),
    ('https://hooks.slack.com/services/T123/B456/token789/extra', False),
    ('https://user:secret@hooks.slack.com/services/T123/B456/token789', False),
    ('https://hooks.slack.com:444/services/T123/B456/token789', False),
    ('https://[broken', False),
])
def test_slack_webhook_url_is_origin_and_path_scoped(url: str, approved: bool) -> None:
    assert slack._valid_webhook_url(url) is approved


def test_slack_parser_preserves_encrypted_existing_secret() -> None:
    old = SimpleNamespace(credential_payload='{"webhook_url":"' + WEBHOOK + '"}', destination='ops')
    parsed = slack.parse_form(
        MultiDict({'slack_destination': 'Platform / Alerts', 'slack_webhook_url': ''}), old,
    )
    assert parsed[1] == {'webhook_url': WEBHOOK}
    assert not parsed[3]
    assert slack.form_view(old) == {'slack_destination': 'ops'}


def test_slack_posts_sanitized_content_and_does_not_follow_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = Mock()
    reply = MagicMock()
    reply.status = 200
    reply.read.return_value = b'ok'
    opener.open.return_value = reply
    handlers = []
    def fake_build(*args: object) -> Mock:
        handlers.extend(args)
        return opener
    monkeypatch.setattr(slack, 'build_opener', fake_build)
    result = slack.send_slack_message(
        credentials={'webhook_url': WEBHOOK}, destination='Platform / Alerts',
        provider_config={}, message=_message(),
    )
    assert result.success
    assert any(isinstance(item, slack.DenyRedirects) for item in handlers)
    request = opener.open.call_args.args[0]
    assert request.full_url == WEBHOOK
    assert b'&lt;!here&gt;' in request.data
    assert b'&lt;@U123&gt;' in request.data


def test_slack_rate_limit_and_redirect_do_not_leak_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = Mock()
    opener.open.side_effect = HTTPError(WEBHOOK, 429, 'Limited', {}, None)
    monkeypatch.setattr(slack, 'build_opener', lambda *_items: opener)
    result = slack.send_slack_message(
        credentials={'webhook_url': WEBHOOK}, destination='Ops',
        provider_config={}, message=_message(),
    )
    assert not result.success and '429' in result.message and 'token789' not in result.message
    assert slack.DenyRedirects().redirect_request(
        Request(WEBHOOK), None, 302, 'Found', {}, 'http://127.0.0.1/',
    ) is None
    opener.open.side_effect = HTTPError(WEBHOOK, 302, 'Redirect', {}, None)
    assert 'HTTP 302' in slack.send_slack_message(
        credentials={'webhook_url': WEBHOOK}, destination='Ops',
        provider_config={}, message=_message(),
    ).message


def test_slack_invalid_destination_rejected_without_transport() -> None:
    data = SimpleNamespace(destination='Ops', credentials={'webhook_url': 'http://internal'}, provider_config={})
    assert slack.validate_form(data)

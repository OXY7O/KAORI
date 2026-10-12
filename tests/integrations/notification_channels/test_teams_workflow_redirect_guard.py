from __future__ import annotations

from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from app.integrations.delivery.notification_channels.contracts import NotificationMessage
from app.integrations.delivery.notification_channels.providers import microsoft_teams as teams

WORKFLOW_URL = 'https://abc.1.environment.api.powerplatform.com/workflow/token'


@pytest.mark.parametrize('url,expected', [
    (WORKFLOW_URL, True),
    ('http://abc.1.environment.api.powerplatform.com/workflow/token', False),
    ('https://localhost/secret', False),
    ('https://malicious.example/path', False),
    ('https://name:pass@abc.1.environment.api.powerplatform.com/workflow/token', False),
    ('https://abc.1.environment.api.powerplatform.com:444/secret', False),
    ('https://[bad-host', False),
    ('https://abc.1.environment.api.powerplatform.com:notaport/secret', False),
])
def test_workflow_url_validation(url: str, expected: bool) -> None:
    assert teams._is_approved_workflow_url(url) is expected


def test_redirect_to_unapproved_destination_is_not_followed() -> None:
    handler = teams._NoWorkflowRedirects()
    assert handler.redirect_request(Request(WORKFLOW_URL), None, 302, 'Redirect', {},
                                    'http://localhost/private') is None


def test_workflow_redirect_returns_safe_failure_without_forwarding_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = Mock()
    opener.open.side_effect = HTTPError(WORKFLOW_URL, 302, 'Found', {'Location': 'http://localhost'}, None)
    built: list[object] = []

    def opener_factory(handler: object) -> Mock:
        built.append(handler)
        return opener

    monkeypatch.setattr(teams, 'build_opener', opener_factory)
    result = teams.send_microsoft_teams_message(
        credentials={'workflow_url': WORKFLOW_URL},
        destination='Operations',
        provider_config={},
        message=NotificationMessage(title='Test', body='Ready', severity='info'),
    )
    assert not result.success
    assert 'HTTP 302' in result.message
    assert len(built) == 1
    assert isinstance(built[0], teams._NoWorkflowRedirects)
    assert opener.open.call_count == 1
    assert 'localhost' not in result.message

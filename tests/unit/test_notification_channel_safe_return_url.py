"""Notification Channel POST/redirect filter serialization remains same-origin."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask

from app.integrations.delivery.notification_channels import routes


@pytest.fixture
def app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.register_blueprint(routes.notification_channels_bp)
    return flask_app


def test_return_url_keeps_bounded_form_filters_as_query_data(app: Flask) -> None:
    with app.test_request_context(
        '/',
        method='POST',
        data={
            'channel_search': '  team & shared  ',
            'channel_provider': 'email',
            'channel_state': 'ready',
            'channel_lifecycle': 'retired',
            'channel_page': '12',
            'channel_per_page': '25',
            '_external': 'https://external.invalid',
        },
    ):
        target = routes._channel_return_url()

    url = urlsplit(target)
    params = parse_qs(url.query)
    assert url.scheme == ''
    assert url.netloc == ''
    assert url.path == '/integrations/notification-channels/'
    assert params == {
        'tab': ['channels'],
        'channel_search': ['team & shared'],
        'channel_provider': ['email'],
        'channel_state': ['ready'],
        'channel_lifecycle': ['retired'],
        'channel_page': ['12'],
        'channel_per_page': ['25'],
    }


@pytest.mark.parametrize(
    ('overrides', 'expected'),
    [
        ({'configure': 1, 'provider': 'webhook'}, {'configure': ['1'], 'provider': ['webhook']}),
        ({'edit': 14, 'configure': 1}, {'edit': ['14'], 'configure': ['1']}),
        ({'channel_lifecycle': 'retired'}, {'channel_lifecycle': ['retired']}),
    ],
)
def test_return_url_keeps_action_and_lifecycle_override(
    app: Flask, overrides: dict[str, str | int], expected: dict[str, list[str]]
) -> None:
    with app.test_request_context(
        '/',
        method='POST',
        data={'channel_lifecycle': 'retired', 'channel_page': '8'},
    ):
        target = routes._channel_return_url(**overrides)

    params = parse_qs(urlsplit(target).query)
    assert params['tab'] == ['channels']
    assert params['channel_page'] == ['8']
    for name, value in expected.items():
        assert params[name] == value


def test_return_url_discards_invalid_or_unbounded_page_and_unknown_fields(app: Flask) -> None:
    with app.test_request_context(
        '/',
        method='POST',
        data={
            'channel_search': 'x' * 150,
            'channel_page': '-3',
            'channel_per_page': '999999',
            'untrusted_redirect': 'https://external.invalid',
        },
    ):
        target = routes._channel_return_url()

    params = parse_qs(urlsplit(target).query)
    assert params['channel_search'] == ['x' * 128]
    assert params['channel_per_page'] == ['1000']
    assert 'channel_page' not in params
    assert 'untrusted_redirect' not in params
    assert params['tab'] == ['channels']

"""Preserve Notification Channel return filters as same-origin URL data."""

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


def test_create_rejection_keeps_form_filters_without_untrusted_controls(app: Flask) -> None:
    form = {
        'channel_search': 'team alerts',
        'channel_provider': 'smtp',
        'channel_page': '7',
        'channel_per_page': '5',
        '_external': 'https://untrusted.test',
    }
    with app.test_request_context('/', method='POST', data=form):
        result = routes._channel_return_url(configure=1, provider='smtp')

    parsed = urlsplit(result)
    query = parse_qs(parsed.query)
    assert parsed.scheme == ''
    assert parsed.netloc == ''
    assert parsed.path == '/integrations/notification-channels/'
    assert query['tab'] == ['channels']
    assert query['configure'] == ['1']
    assert query['provider'] == ['smtp']
    assert query['channel_search'] == ['team alerts']
    assert query['channel_page'] == ['7']
    assert query['channel_per_page'] == ['5']
    assert '_external' not in query


def test_rejected_update_preserves_edit_identity_and_encodes_provider(app: Flask) -> None:
    with app.test_request_context('/', method='POST', data={'channel_lifecycle': 'retired'}):
        target = routes._channel_return_url(edit=19, configure=1, provider='smtp&tab=other')

    query = parse_qs(urlsplit(target).query)
    assert query['edit'] == ['19']
    assert query['configure'] == ['1']
    assert query['channel_lifecycle'] == ['retired']
    assert query['provider'] == ['smtp&tab=other']
    assert query['tab'] == ['channels']


def test_retired_lifecycle_override_preserves_pagination_limit(app: Flask) -> None:
    with app.test_request_context('/', method='POST', data={'channel_page': '2000', 'channel_per_page': '10'}):
        target = routes._channel_return_url(channel_lifecycle='retired')

    query = parse_qs(urlsplit(target).query)
    assert query['channel_lifecycle'] == ['retired']
    assert query['channel_page'] == ['1000']
    assert query['channel_per_page'] == ['10']


def test_default_redirect_returns_channels_tab_only(app: Flask) -> None:
    with app.test_request_context('/', method='POST', data={}):
        target = routes._channel_return_url()

    assert parse_qs(urlsplit(target).query) == {'tab': ['channels']}

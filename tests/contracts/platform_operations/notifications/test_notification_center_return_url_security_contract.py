"""Notifications mutation redirects may return only to the canonical Center route."""

from __future__ import annotations

import pytest
from flask import Flask

from app.platform_operations.notifications.routes import _notification_center_return_url


@pytest.fixture
def center_app() -> Flask:
    app = Flask(__name__)
    app.add_url_rule('/notifications/', endpoint='notifications.center', view_func=lambda: 'ok')
    return app


@pytest.mark.parametrize(
    ('candidate', 'expected'),
    [
        ('/notifications/', '/notifications/'),
        (
            '/notifications/?view=notifications&page=3&status=all',
            '/notifications/?view=notifications&page=3&status=all',
        ),
        ('/notifications/?search=hello%20world', '/notifications/?search=hello+world'),
        ('/notifications/?category=&category=system', '/notifications/?category=&category=system'),
        ('/notifications/?', '/notifications/'),
        (' /notifications/ ', '/notifications/'),
        ('/notifications', '/notifications/'),
        ('/notifications/other?view=notifications', '/notifications/'),
        ('/notifications/extra', '/notifications/'),
        ('/reports/generated?status=ready', '/notifications/'),
        ('/notifications/?page=2#other', '/notifications/'),
        ('https://outside.example.invalid/notifications/', '/notifications/'),
        ('//outside.example.invalid/notifications/', '/notifications/'),
        ('/\\outside.example.invalid/notifications/', '/notifications/'),
        ('/notifications/\r\nLocation: https://outside.example.invalid', '/notifications/'),
        (None, '/notifications/'),
        (17, '/notifications/'),
    ],
)
def test_notification_center_return_is_server_owned(
    center_app: Flask,
    candidate: object,
    expected: str,
) -> None:
    with center_app.test_request_context('/'):
        assert _notification_center_return_url(candidate) == expected

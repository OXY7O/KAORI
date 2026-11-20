"""Reports Schedules post-action returns never redirect to a request-owned path."""

from __future__ import annotations

from typing import cast

import pytest
from flask import Flask

from app.reports.schedules.routes import _schedule_query_args, _schedule_return_url

REGISTRY = '/reports/schedules'


@pytest.fixture
def schedules_app() -> Flask:
    app = Flask(__name__)
    app.add_url_rule(REGISTRY, endpoint='reports.schedules', view_func=lambda: 'ok')
    return app


@pytest.mark.parametrize(
    ('candidate', 'expected'),
    [
        (REGISTRY, REGISTRY),
        ('/reports/schedules?', REGISTRY),
        (' /reports/schedules ', REGISTRY),
        ('/reports/schedules?tab=runs&per_page=5', '/reports/schedules?tab=runs&per_page=5'),
        ('/reports/schedules?status=active&status=paused', '/reports/schedules?status=active&status=paused'),
        ('/reports/schedules?status=&page=2', '/reports/schedules?status=&page=2'),
        ('/reports/schedules?edit_schedule_id=9&tab=runs', '/reports/schedules?tab=runs'),
        ('/reports/schedules?edit_schedule_id=9', REGISTRY),
        ('/reports/schedules?search=A%26B', '/reports/schedules?search=A%26B'),
        (
            '/reports/schedules?next=https://outside.example.invalid',
            '/reports/schedules?next=https%3A%2F%2Foutside.example.invalid',
        ),
        ('/reports/schedules-extra?tab=runs', REGISTRY),
        ('/reports/schedules/other?tab=runs', REGISTRY),
        ('/reports/schedules/../schedules', REGISTRY),
        ('/other/reports/schedules?tab=runs', REGISTRY),
        ('/reports/schedules%2Fother?tab=runs', REGISTRY),
        ('/reports/schedules#fragment', REGISTRY),
        ('/reports/schedules?tab=runs#fragment', REGISTRY),
        ('https://outside.example.invalid/reports/schedules', REGISTRY),
        ('//outside.example.invalid/reports/schedules', REGISTRY),
        ('/\\outside.example.invalid/reports/schedules', REGISTRY),
        ('/reports/schedules\r\nLocation: https://outside.example.invalid', REGISTRY),
        ('', REGISTRY),
        (None, REGISTRY),
        (3, REGISTRY),
    ],
)
def test_return_url_uses_only_owned_route(
    schedules_app: Flask, candidate: object, expected: str
) -> None:
    with schedules_app.test_request_context('/'):
        assert _schedule_return_url(cast(str | None, candidate)) == expected


def test_schedule_query_args_remain_filtered_data(schedules_app: Flask) -> None:
    with schedules_app.test_request_context('/'):
        assert _schedule_query_args(
            '/reports/schedules?tab=runs&edit_schedule_id=9&status=ready&status=paused'
        ) == {'tab': 'runs', 'status': 'paused'}
        assert _schedule_query_args('https://outside.example.invalid/redirect?status=ready') == {}

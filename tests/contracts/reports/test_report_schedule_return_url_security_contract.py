"""Report Schedules mutation return targets must remain exact same-origin registry paths."""

from __future__ import annotations

import pytest
from flask import Flask

from app.reports.schedules.routes import _schedule_query_args, _schedule_return_url

REGISTRY = '/reports/schedules'


@pytest.fixture
def schedules_app() -> Flask:
    app = Flask(__name__)
    app.add_url_rule(REGISTRY, endpoint='reports.schedules', view_func=lambda: 'Schedule registry')
    return app


@pytest.mark.parametrize(
    ('candidate', 'expected'),
    [
        (REGISTRY, REGISTRY),
        (f'{REGISTRY}?status=active&period=30d', f'{REGISTRY}?status=active&period=30d'),
        (f'{REGISTRY}?status=active&search=', f'{REGISTRY}?status=active&search='),
        (f'{REGISTRY}?edit_schedule_id=42&status=active', f'{REGISTRY}?status=active'),
        (f'{REGISTRY}?edit_schedule_id=42', REGISTRY),
        (f' {REGISTRY} ', REGISTRY),
        (f'{REGISTRY}#fragment', REGISTRY),
        (f'{REGISTRY}?status=active#fragment', f'{REGISTRY}?status=active'),
        (f'{REGISTRY}-other?status=active', REGISTRY),
        (f'{REGISTRY}/other?status=active', REGISTRY),
        (f'{REGISTRY}/../schedules', REGISTRY),
        (f'/other{REGISTRY}?status=active', REGISTRY),
        (f'https://outside.example.invalid{REGISTRY}?status=active', REGISTRY),
        (f'//outside.example.invalid{REGISTRY}', REGISTRY),
        (f'/\\outside.example.invalid{REGISTRY}', REGISTRY),
        (f'{REGISTRY}\r\nLocation: https://outside.example.invalid', REGISTRY),
        (None, REGISTRY),
    ],
)
def test_schedule_return_resolves_only_exact_safe_registry_path(
    schedules_app: Flask,
    candidate: str | None,
    expected: str,
) -> None:
    with schedules_app.test_request_context('/'):
        assert _schedule_return_url(candidate) == expected


def test_schedule_query_args_removes_edit_state_and_preserves_filters(schedules_app: Flask) -> None:
    with schedules_app.test_request_context('/'):
        assert _schedule_query_args(
            f'{REGISTRY}?status=active&search=&edit_schedule_id=42&period=30d'
        ) == {'status': 'active', 'search': '', 'period': '30d'}
        assert _schedule_query_args('https://outside.example.invalid/reports/schedules') == {}

"""Generated Reports return URLs must reference the exact internal registry route."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from flask import Flask

from app.reports.export.routes import _generated_registry_return_url as export_registry_return_url
from app.reports.generated.routes import _generated_registry_return_url as generated_registry_return_url

REGISTRY = '/reports/generated'


@pytest.fixture
def registry_app() -> Flask:
    app = Flask(__name__)
    app.add_url_rule(REGISTRY, endpoint='reports.generated_reports', view_func=lambda: 'ok')
    return app


@pytest.mark.parametrize(
    'resolve',
    [generated_registry_return_url, export_registry_return_url],
    ids=['generated-reports', 'report-export'],
)
@pytest.mark.parametrize(
    ('candidate', 'expected'),
    [
        (REGISTRY, REGISTRY),
        ('/reports/generated?period=7d&status=ready', '/reports/generated?period=7d&status=ready'),
        ('/reports/generated?', REGISTRY),
        ('/reports/generated?search=hello%20world', '/reports/generated?search=hello+world'),
        ('/reports/generated?scope=a&scope=b', '/reports/generated?scope=a&scope=b'),
        ('/reports/generated?status=', '/reports/generated?status='),
        ('/reports/generated?next=%2F%2Foutside.example.invalid',
         '/reports/generated?next=%2F%2Foutside.example.invalid'),
        ('/reports/generated?status=ready#redirect', REGISTRY),
        (' /reports/generated ', REGISTRY),
        ('/reports/generated-extra?period=7d', REGISTRY),
        ('/reports/generated/other?period=7d', REGISTRY),
        ('/reports/generated#fragment', REGISTRY),
        ('/reports/generated/../generated', REGISTRY),
        ('/other/reports/generated?period=7d', REGISTRY),
        ('https://outside.example.invalid/reports/generated', REGISTRY),
        ('//outside.example.invalid/reports/generated', REGISTRY),
        ('/\\outside.example.invalid/reports/generated', REGISTRY),
        ('/reports/generated\r\nLocation: https://outside.example.invalid', REGISTRY),
        (None, REGISTRY),
        (1, REGISTRY),
    ],
)
def test_registry_return_requires_exact_safe_path(
    registry_app: Flask,
    resolve: Callable[[object], str],
    candidate: object,
    expected: str,
) -> None:
    with registry_app.test_request_context('/'):
        assert resolve(candidate) == expected

"""Report Templates return navigation uses only its server-owned registry path."""

from __future__ import annotations

from typing import cast
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask

from app.reports.report_templates.routes import (
    _template_edit_url,
    _template_registry_return_url,
    _template_registry_url_without_edit,
)

REGISTRY = '/reports/templates'


@pytest.fixture
def templates_app() -> Flask:
    app = Flask(__name__)
    app.add_url_rule(REGISTRY, endpoint='reports.report_templates', view_func=lambda: 'ok')
    return app


@pytest.mark.parametrize(
    ('candidate', 'expected'),
    [
        (REGISTRY, REGISTRY),
        ('/reports/templates?', REGISTRY),
        (' /reports/templates ', REGISTRY),
        ('/reports/templates?search=alpha&status=active', '/reports/templates?search=alpha&status=active'),
        ('/reports/templates?edit_template_id=7&tab=custom', '/reports/templates?edit_template_id=7&tab=custom'),
        ('/reports/templates?status=active&status=draft', '/reports/templates?status=active&status=draft'),
        ('/reports/templates?search=%3Cscript%3E', '/reports/templates?search=%3Cscript%3E'),
        (
            '/reports/templates?next=https://outside.example.invalid',
            '/reports/templates?next=https://outside.example.invalid',
        ),
        ('/reports/templates-extra?status=active', REGISTRY),
        ('/reports/templates/extra?status=active', REGISTRY),
        ('/reports/templates/../templates', REGISTRY),
        ('/other/reports/templates?status=active', REGISTRY),
        ('/reports/templates%2Fextra?status=active', REGISTRY),
        ('/reports/templates#fragment', REGISTRY),
        ('/reports/templates?status=active#fragment', REGISTRY),
        ('https://outside.example.invalid/reports/templates', REGISTRY),
        ('//outside.example.invalid/reports/templates', REGISTRY),
        ('/\\outside.example.invalid/reports/templates', REGISTRY),
        ('/reports/templates\r\nLocation: https://outside.example.invalid', REGISTRY),
        ('', REGISTRY),
        (None, REGISTRY),
        (3, REGISTRY),
    ],
)
def test_templates_return_is_exact_owned_route(templates_app: Flask, candidate: object, expected: str) -> None:
    with templates_app.test_request_context('/'):
        actual = _template_registry_return_url(cast(str | None, candidate))
        assert actual == expected
        assert urlsplit(actual).path == REGISTRY
        assert urlsplit(actual).scheme == ''
        assert urlsplit(actual).netloc == ''


def test_template_edit_and_exit_keep_filtered_registry_state(templates_app: Flask) -> None:
    with templates_app.test_request_context('/'):
        registry = _template_registry_return_url(
            '/reports/templates?search=A%26B&status=active&edit_template_id=4'
        )
        edit = _template_edit_url(registry, 9)
        assert urlsplit(edit).path == REGISTRY
        assert parse_qs(urlsplit(edit).query) == {
            'search': ['A&B'],
            'status': ['active'],
            'edit_template_id': ['9'],
        }
        exit_url = _template_registry_url_without_edit(edit)
        assert urlsplit(exit_url).path == REGISTRY
        assert parse_qs(urlsplit(exit_url).query) == {
            'search': ['A&B'],
            'status': ['active'],
        }

"""Verify Notification Center Routes honors server-backed Rows request parameters."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask

from app.platform_operations.notifications import routes


@pytest.mark.parametrize('per_page', (5, 10, 25, 50))
def test_notification_rows_request_forwards_page_size_and_active_filters(
    monkeypatch: pytest.MonkeyPatch, per_page: int
) -> None:
    app = Flask(__name__)
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        routes,
        'current_user',
        SimpleNamespace(id=42, has_permission=lambda permission: permission == 'jobs.view'),
    )

    def capture_context(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {'notification_pagination': {'per_page': kwargs['per_page']}}

    monkeypatch.setattr(routes, 'get_notification_center_page_context', capture_context)

    with app.test_request_context(
        f'/notifications/?view=notifications&page=1&per_page={per_page}'
        '&search=artifact&category=all&status=success&read_state=read',
        headers={'HX-Request': 'true'},
    ):
        result = routes._center_page_context()

    assert result['notification_pagination']['per_page'] == per_page
    assert captured == {
        'user_id': 42,
        'page': 1,
        'per_page': per_page,
        'job_limit': routes.ACTIVITY_CENTER_PAGE_LIMIT,
        'include_all_jobs': True,
        'status': 'success',
        'read_state': 'read',
        'category': 'all',
        'search': 'artifact',
    }


def test_missing_rows_query_still_defaults_to_five(monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        routes,
        'current_user',
        SimpleNamespace(id=42, has_permission=lambda permission: False),
    )
    monkeypatch.setattr(
        routes,
        'get_notification_center_page_context',
        lambda **kwargs: captured.update(kwargs) or {},
    )

    with app.test_request_context('/notifications/?view=notifications'):
        routes._center_page_context()

    assert captured['per_page'] == 5
    assert captured['include_all_jobs'] is False

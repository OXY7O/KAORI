"""Non-HTMX cluster sync-dismiss redirects must not trust the Referer origin."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask, make_response
from redis.exceptions import RedisError

from app.kubernetes.cluster import routes


@pytest.fixture
def redirect_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = 'isolated-test-only-secret'
    app.add_url_rule(
        '/integrations/kubernetes',
        endpoint='integrations.kubernetes',
        view_func=lambda: '',
    )
    return app


@pytest.mark.parametrize('redis_unavailable', (False, True))
@pytest.mark.parametrize(
    ('referrer', 'expected_location'),
    [
        ('/integrations/kubernetes?tab=clusters', '/integrations/kubernetes?tab=clusters'),
        ('https://outside.example.invalid/redirect', '/integrations/kubernetes'),
        ('//outside.example.invalid/redirect', '/integrations/kubernetes'),
        ('/\\outside.example.invalid', '/integrations/kubernetes'),
        ('/integrations/kubernetes\r\nLocation: https://outside.example.invalid', '/integrations/kubernetes'),
        ('', '/integrations/kubernetes'),
    ],
)
def test_sync_dismiss_return_is_same_origin(
    monkeypatch: pytest.MonkeyPatch,
    redirect_app: Flask,
    redis_unavailable: bool,
    referrer: str,
    expected_location: str,
) -> None:
    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=42))
    monkeypatch.setattr(routes, 'build_cluster_sync_snapshot', lambda _task_id: {'is_active': False})

    def dismiss_result(**_kwargs: object) -> None:
        if redis_unavailable:
            raise RedisError('isolated unavailable state')

    monkeypatch.setattr(routes, 'dismiss_cluster_sync_result', dismiss_result)

    with redirect_app.test_request_context(
        '/clusters/sync-all/status/task-123/dismiss',
        method='POST',
        headers={'Referer': referrer},
    ):
        # Authentication/permission decorators have separate contracts; this
        # verifies the actual handler's response without database or Redis.
        response = make_response(routes.dismiss_sync_all_status.__wrapped__('task-123'))

    assert response.status_code == 302
    assert response.headers['Location'] == expected_location


@pytest.mark.parametrize(('redis_unavailable', 'status'), [(False, 200), (True, 503)])
def test_sync_dismiss_htmx_has_no_redirect(
    monkeypatch: pytest.MonkeyPatch,
    redirect_app: Flask,
    redis_unavailable: bool,
    status: int,
) -> None:
    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=42))
    monkeypatch.setattr(routes, 'build_cluster_sync_snapshot', lambda _task_id: {'is_active': False})

    def dismiss_result(**_kwargs: object) -> None:
        if redis_unavailable:
            raise RedisError('isolated unavailable state')

    monkeypatch.setattr(routes, 'dismiss_cluster_sync_result', dismiss_result)

    with redirect_app.test_request_context(
        '/clusters/sync-all/status/task-123/dismiss',
        method='POST',
        headers={
            'Referer': 'https://outside.example.invalid/redirect',
            'HX-Request': 'true',
        },
    ):
        response = make_response(routes.dismiss_sync_all_status.__wrapped__('task-123'))

    assert response.status_code == status
    assert response.headers.get('Location') is None

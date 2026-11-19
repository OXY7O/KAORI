"""Kubernetes inventory POST actions preserve KAORI's safe relative redirect contract."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, make_response

from app.access.authentication.session import safe_next_url

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ('referrer', 'expected'),
    [
        ('/integrations/kubernetes', '/integrations/kubernetes'),
        ('/inventory/?cluster_id=1', '/inventory/?cluster_id=1'),
        ('https://external.example.invalid/phishing', None),
        ('//external.example.invalid/phishing', None),
        ('/\\external.example.invalid', None),
        ('/inventory/\r\nLocation: https://external.example.invalid', None),
    ],
)
def test_reused_safe_next_url_rejects_cross_origin_referrers(referrer: str, expected: str | None) -> None:
    assert safe_next_url(referrer) == expected


@pytest.mark.parametrize(
    ('source_path', 'guarded_redirects'),
    [
        ('app/kubernetes/inventory/routes.py', 2),
        ('app/kubernetes/cluster/quick_sync.py', 4),
    ],
)
def test_kubernetes_sync_actions_guard_all_referrer_redirects(source_path: str, guarded_redirects: int) -> None:
    source = (ROOT / source_path).read_text(encoding='utf-8')
    assert 'from app.access.authentication.session import safe_next_url' in source
    assert source.count('safe_next_url(request.referrer)') == guarded_redirects
    assert 'redirect(request.referrer or ' not in source


@pytest.fixture
def redirect_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = 'synthetic-redirect-contract'
    app.add_url_rule('/integrations/kubernetes', endpoint='integrations.kubernetes', view_func=lambda: '')
    app.add_url_rule(
        '/integrations/kubernetes/<int:cluster_id>',
        endpoint='integrations.kubernetes_detail',
        view_func=lambda cluster_id: 'ok',
    )
    return app


@pytest.mark.parametrize('cluster_id', (1, 19))
def test_synthetic_cluster_detail_is_static(redirect_app: Flask, cluster_id: int) -> None:
    response = redirect_app.test_client().get(f'/integrations/kubernetes/{cluster_id}')
    assert response.status_code == 200
    assert response.get_data(as_text=True) == 'ok'


@pytest.mark.parametrize('flow', ('empty', 'accepted', 'blocked', 'enqueue_error'))
@pytest.mark.parametrize(
    ('referrer', 'expected_location'),
    [
        ('/inventory/?cluster_id=19', '/inventory/?cluster_id=19'),
        ('https://external.example.invalid/phishing', '/integrations/kubernetes'),
        ('//external.example.invalid/phishing', '/integrations/kubernetes'),
        ('/\\external.example.invalid', '/integrations/kubernetes'),
    ],
)
def test_global_sync_redirect_response_is_same_origin(
    monkeypatch: pytest.MonkeyPatch,
    redirect_app: Flask,
    flow: str,
    referrer: str,
    expected_location: str,
) -> None:
    from app.kubernetes.cluster import quick_sync

    monkeypatch.setattr(quick_sync, 'current_user', SimpleNamespace(id=17))
    monkeypatch.setattr(
        quick_sync,
        'Cluster',
        SimpleNamespace(query=SimpleNamespace(count=lambda: 0 if flow == 'empty' else 1)),
    )
    monkeypatch.setattr(quick_sync, 'record_operational_activity', lambda **_kwargs: None)

    def dispatch(**_kwargs: object) -> SimpleNamespace:
        if flow == 'enqueue_error':
            raise RuntimeError('synthetic dispatch rejection')
        return SimpleNamespace(
            accepted=flow == 'accepted',
            job=object() if flow == 'accepted' else None,
            created=True,
            status='blocked',
            message='synthetic no eligible cluster',
        )

    monkeypatch.setattr(quick_sync, 'dispatch_registered_job', dispatch)

    with redirect_app.test_request_context(
        '/inventory/global-sync',
        method='POST',
        headers={'Referer': referrer},
    ):
        response = make_response(quick_sync.run_global_inventory_sync())

    assert response.status_code == 302
    assert response.headers['Location'] == expected_location


@pytest.mark.parametrize(
    ('flow', 'expected_status'), [('empty', 204), ('accepted', 202), ('blocked', 204), ('enqueue_error', 204)]
)
def test_global_sync_htmx_keeps_original_status_without_redirect(
    monkeypatch: pytest.MonkeyPatch, redirect_app: Flask, flow: str, expected_status: int
) -> None:
    from app.kubernetes.cluster import quick_sync

    monkeypatch.setattr(quick_sync, 'current_user', SimpleNamespace(id=17))
    monkeypatch.setattr(
        quick_sync,
        'Cluster',
        SimpleNamespace(query=SimpleNamespace(count=lambda: 0 if flow == 'empty' else 1)),
    )
    monkeypatch.setattr(quick_sync, 'record_operational_activity', lambda **_kwargs: None)

    def dispatch(**_kwargs: object) -> SimpleNamespace:
        if flow == 'enqueue_error':
            raise RuntimeError('synthetic dispatch rejection')
        return SimpleNamespace(
            accepted=flow == 'accepted',
            job=object() if flow == 'accepted' else None,
            created=True,
            status='blocked',
            message='synthetic no eligible cluster',
        )

    monkeypatch.setattr(quick_sync, 'dispatch_registered_job', dispatch)

    with redirect_app.test_request_context(
        '/inventory/global-sync',
        method='POST',
        headers={'Referer': 'https://external.example.invalid/phishing', 'HX-Request': 'true'},
    ):
        response = make_response(quick_sync.run_global_inventory_sync())

    assert response.status_code == expected_status
    assert response.headers.get('Location') is None
    assert response.headers['Cache-Control'] == 'no-store, max-age=0'


@pytest.mark.parametrize('enqueue_error', (False, True))
@pytest.mark.parametrize(
    ('referrer', 'expected_location'),
    [
        ('/inventory/?cluster_id=19', '/inventory/?cluster_id=19'),
        ('https://external.example.invalid/phishing', '/integrations/kubernetes'),
        ('//external.example.invalid/phishing', '/integrations/kubernetes'),
        ('/\\external.example.invalid', '/integrations/kubernetes'),
    ],
)
def test_cluster_sync_redirect_response_is_same_origin(
    monkeypatch: pytest.MonkeyPatch,
    redirect_app: Flask,
    enqueue_error: bool,
    referrer: str,
    expected_location: str,
) -> None:
    from app.kubernetes.inventory import routes

    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=17))
    monkeypatch.setattr(routes, 'get_cluster_by_id', lambda _id: SimpleNamespace(id=19, name='test-cluster'))
    monkeypatch.setattr(routes, 'record_operational_activity', lambda **_kwargs: {'status': 'error'})
    monkeypatch.setattr(routes, 'queue_operational_feedback', lambda _feedback: None)

    def enqueue(**_kwargs: object) -> tuple[SimpleNamespace, bool]:
        if enqueue_error:
            raise RuntimeError('synthetic enqueue rejection')
        return SimpleNamespace(queued_at=None, started_at=None, celery_task_id='test-task', id=23), True

    monkeypatch.setattr(routes, 'enqueue_cluster_inventory_sync', enqueue)

    with redirect_app.test_request_context(
        '/inventory/19/sync',
        method='POST',
        headers={'Referer': referrer},
    ):
        # The security contract tests the handler after the existing RBAC decorator.
        response = make_response(routes.sync.__wrapped__('19'))

    assert response.status_code == 302
    assert response.headers['Location'] == expected_location


@pytest.mark.parametrize(('enqueue_error', 'expected_status'), [(False, 202), (True, 503)])
def test_cluster_sync_htmx_preserves_fragment_response(
    monkeypatch: pytest.MonkeyPatch,
    redirect_app: Flask,
    enqueue_error: bool,
    expected_status: int,
) -> None:
    from app.kubernetes.inventory import routes

    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=17))
    monkeypatch.setattr(routes, 'get_cluster_by_id', lambda _id: SimpleNamespace(id=19, name='test-cluster'))
    monkeypatch.setattr(routes, 'record_operational_activity', lambda **_kwargs: {'status': 'error'})
    monkeypatch.setattr(routes, 'get_navigation_notification_context', lambda **_kwargs: {})
    monkeypatch.setattr(routes, 'render_template', lambda _template, **_kwargs: '<div>test-fragment</div>')

    def enqueue(**_kwargs: object) -> tuple[SimpleNamespace, bool]:
        if enqueue_error:
            raise RuntimeError('synthetic enqueue rejection')
        return SimpleNamespace(queued_at=None, started_at=None, celery_task_id='test-task', id=23), True

    monkeypatch.setattr(routes, 'enqueue_cluster_inventory_sync', enqueue)

    with redirect_app.test_request_context(
        '/inventory/19/sync',
        method='POST',
        headers={'Referer': 'https://external.example.invalid/phishing', 'HX-Request': 'true'},
    ):
        response = make_response(routes.sync.__wrapped__('19'))

    assert response.status_code == expected_status
    assert response.headers.get('Location') is None
    assert response.data == b'<div>test-fragment</div>'

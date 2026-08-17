from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import login as login_extension
from app.extensions import login_manager
from app.kubernetes.operations import operation_flow
from app.kubernetes.operations.configmaps import routes as configmap_routes
from app.kubernetes.operations.secrets import crud_routes as secret_routes


class OperationsSmokeUser(UserMixin):
    id = 72
    username = 'operations-smoke'
    display_label = 'Operations Smoke'
    role_name = 'operations_test'
    role_display_name = 'Operations Test'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def get_id(self) -> str:
        return 'operations-smoke'

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in {
            'kubernetes_configmaps.view',
            'kubernetes_configmaps.create',
            'kubernetes_configmaps.update',
            'kubernetes_configmaps.delete',
            'kubernetes_secrets.view',
            'kubernetes_secrets.create',
            'kubernetes_secrets.replace',
            'kubernetes_secrets.delete',
            'kubernetes_secrets.reveal',
            'kubernetes_secrets.approve_reveal',
            'kubernetes_secrets.rotate_tls',
            'kubernetes_secrets.bulk_rotate_tls',
            'jobs.view',
            'clusters.manage',
        }


def _empty_navigation_context() -> dict[str, object]:
    return {
        'items': [],
        'history_items': [],
        'attention_items': [],
        'active_jobs': [],
        'active_count': 0,
        'attention_count': 0,
        'unread_count': 0,
        'total_count': 0,
        'display_limit': 8,
        'job_display_limit': 6,
    }


def _cluster_context() -> dict[str, object]:
    return {
        'show_banner': False,
        'is_kubernetes_scope': True,
        'is_blocked': False,
        'has_clusters': True,
        'cluster_count': 1,
        'can_manage_clusters': True,
        'database_ready': True,
    }


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        login_extension,
        'check_authentication_database_readiness',
        lambda: SimpleNamespace(ready=True),
    )
    monkeypatch.setattr(bootstrap_presentation, 'build_cluster_onboarding_context', _cluster_context)
    monkeypatch.setattr(
        bootstrap_presentation,
        'get_navigation_notification_context',
        lambda **_kwargs: _empty_navigation_context(),
    )
    monkeypatch.setattr(bootstrap_presentation, 'pop_operational_feedback', lambda: None)
    monkeypatch.setattr(operation_flow, 'has_registered_clusters', lambda: True)
    monkeypatch.setattr(
        configmap_routes,
        'get_context',
        lambda: {'clusters': [], 'total_configmaps': 0, 'namespace_count': 0, 'immutable_count': 0},
    )
    monkeypatch.setattr(
        secret_routes,
        'get_secret_management_overview',
        lambda: {'total': 0, 'tls_count': 0, 'namespace_count': 0, 'cluster_count': 0},
    )
    return create_app('testing')


def test_anonymous_user_is_redirected_before_kubernetes_operations_render(app) -> None:
    response = app.test_client().get('/kubernetes-operations/configmaps')

    assert response.status_code == 302
    assert '/login?next=' in response.headers['Location']


def test_authorized_user_renders_configmap_and_secret_management_in_global_shell(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = OperationsSmokeUser()
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'

    configmap = client.get('/kubernetes-operations/configmaps')
    secret = client.get('/kubernetes-operations/secrets')
    configmap_html = configmap.get_data(as_text=True)
    secret_html = secret.get_data(as_text=True)

    assert configmap.status_code == 200
    assert secret.status_code == 200
    assert 'ConfigMap Management' in configmap_html
    assert 'Secret Management' in secret_html
    assert 'Quick Actions' in configmap_html and 'Notifications' in configmap_html
    assert 'Quick Actions' in secret_html and 'Notifications' in secret_html
    assert 'x-data="kaoriNavbar"' in configmap_html
    assert 'x-data="kaoriNavbar"' in secret_html

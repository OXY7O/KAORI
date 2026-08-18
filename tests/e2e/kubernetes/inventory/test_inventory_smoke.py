from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import login as login_extension
from app.extensions import login_manager
from app.kubernetes.inventory import routes as inventory_routes


class InventorySmokeUser(UserMixin):
    id = 32
    username = 'inventory-smoke'
    display_label = 'Inventory Smoke'
    role_name = 'super_admin'
    role_display_name = 'Super Admin'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def get_id(self) -> str:
        return 'inventory-smoke'

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in {'inventory.view', 'jobs.view', 'clusters.manage'}


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


def _freshness_context() -> dict[str, object]:
    return {
        'source_label': 'Committed Inventory Snapshot',
        'status': 'Current',
        'tone': 'normal',
        'description': 'Current committed snapshot.',
        'latest_collected_at': None,
        'scope_label': 'All Clusters',
        'coverage_label': '1 of 1 snapshots',
        'exception_label': 'No Exceptions',
        'latest_supporting': '24-hour freshness window',
        'scope_supporting': 'Fleet scope',
        'coverage_supporting': 'Fully committed',
        'exceptions_supporting': 'No issues detected',
        'coverage_tone': 'normal',
        'exceptions_tone': 'normal',
    }


def _overview_context() -> dict[str, object]:
    return {
        'total_clusters': 1,
        'inventory_total': 0,
        'asset_catalog': [],
        'active_signal_count': 0,
        'clusters': [],
        'health': {'connected_clusters': 1},
        'posture': {'status': 'Healthy', 'tone': 'normal'},
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
    monkeypatch.setattr(inventory_routes, 'get_inventory_overview', _overview_context)
    monkeypatch.setattr(inventory_routes, 'get_inventory_freshness_context', lambda **_kwargs: _freshness_context())
    return create_app('testing')


def test_anonymous_user_is_redirected_before_inventory_render(app) -> None:
    response = app.test_client().get('/inventory/')

    assert response.status_code == 302
    assert '/login?next=' in response.headers['Location']


def test_authorized_user_renders_inventory_overview_in_global_application_shell(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = InventorySmokeUser()
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'

    response = client.get('/inventory/')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Inventory Overview' in html
    assert 'Inventory Asset Catalog' in html
    assert 'Cluster Inventory Summary' in html
    assert 'Quick Actions' in html
    assert 'Notifications' in html
    assert 'x-data="kaoriNavbar"' in html

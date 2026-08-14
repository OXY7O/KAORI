from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import login as login_extension
from app.extensions import login_manager
from app.inventory.kubernetes import routes as inventory_routes


class InventoryRouteUser(UserMixin):
    id = 31
    username = 'inventory-route-test'
    display_label = 'Inventory Route Test'
    role_name = 'inventory_test'
    role_display_name = 'Inventory Test'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def __init__(self, *, allowed: bool) -> None:
        self.allowed = allowed

    def get_id(self) -> str:
        return f'inventory-route-{int(self.allowed)}'

    def has_permission(self, permission_key: str) -> bool:
        return self.allowed and permission_key == 'inventory.view'


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
    monkeypatch.setattr(inventory_routes, 'get_inventory_freshness_context', lambda **_kwargs: _freshness_context())
    return create_app('testing')


def _client_for_user(app, monkeypatch: pytest.MonkeyPatch, user: InventoryRouteUser):
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'
    return client


def test_unauthorized_htmx_inventory_read_is_denied_before_cluster_probe(app, monkeypatch: pytest.MonkeyPatch) -> None:
    user = InventoryRouteUser(allowed=False)
    client = _client_for_user(app, monkeypatch, user)

    def unexpected_cluster_probe() -> bool:
        raise AssertionError('cluster readiness must not be evaluated before inventory.view authorization')

    monkeypatch.setattr(inventory_routes, 'has_registered_clusters', unexpected_cluster_probe)

    response = client.get('/inventory/nodes', headers={'HX-Request': 'true'})

    assert response.status_code == 403


def test_authorized_clusterless_htmx_inventory_read_returns_blocker_without_resource_query(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = InventoryRouteUser(allowed=True)
    client = _client_for_user(app, monkeypatch, user)
    monkeypatch.setattr(inventory_routes, 'has_registered_clusters', lambda: False)

    def unexpected_resource_query(**_kwargs):
        raise AssertionError('clusterless HTMX blocker must run before Inventory resource queries')

    monkeypatch.setattr(inventory_routes, 'get_node_inventory', unexpected_resource_query)

    response = client.get('/inventory/nodes', headers={'HX-Request': 'true'})
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Connect Your First Kubernetes Cluster' in html


def test_inventory_sync_keeps_clusters_sync_as_separate_mutation_permission() -> None:
    routes = Path(inventory_routes.__file__)
    tree = ast.parse(routes.read_text(encoding='utf-8'))
    sync = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'sync')
    decorator_source = ast.unparse(sync.decorator_list[1])

    assert decorator_source == "permission_required('clusters.sync')"

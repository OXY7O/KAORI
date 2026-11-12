from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask_login import UserMixin

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.common.navigation import build_navigation_breadcrumb
from app.common.workspace_navigation import build_capability_navigation
from app.extensions import login as login_extension
from app.extensions import login_manager
from app.kubernetes.governance import routes as governance_routes
from app.kubernetes.governance.internal_certificates import routes as internal_pki_routes
from app.kubernetes.governance.tls_certificates import routes as tls_routes


class GovernanceRouteUser(UserMixin):
    id = 41
    username = 'governance-route-test'
    display_label = 'Governance Route Test'
    role_name = 'governance_test'
    role_display_name = 'Governance Test'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def __init__(self, permissions: set[str]) -> None:
        self.permissions = permissions

    def get_id(self) -> str:
        return 'governance-route-test'

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in self.permissions


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


def _clusterless_context() -> dict[str, object]:
    return {
        'show_banner': True,
        'is_kubernetes_scope': True,
        'is_blocked': True,
        'has_clusters': False,
        'cluster_count': 0,
        'can_manage_clusters': False,
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
    return create_app('testing')


def _client_for_user(app, monkeypatch: pytest.MonkeyPatch, user: GovernanceRouteUser):
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'
    return client


def test_unauthorized_tls_htmx_read_is_denied_before_cluster_probe(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(app, monkeypatch, GovernanceRouteUser(set()))

    def unexpected_cluster_probe() -> bool:
        raise AssertionError('cluster readiness must not run before tls_certificates.view')

    monkeypatch.setattr(tls_routes, 'has_registered_clusters', unexpected_cluster_probe)
    response = client.get('/governance/tls-certificates', headers={'HX-Request': 'true'})
    assert response.status_code == 403


def test_authorized_clusterless_tls_htmx_read_returns_onboarding_before_page_query(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(app, monkeypatch, GovernanceRouteUser({'tls_certificates.view'}))
    monkeypatch.setattr(bootstrap_presentation, 'build_cluster_onboarding_context', _clusterless_context)
    monkeypatch.setattr(tls_routes, 'has_registered_clusters', lambda: False)

    def unexpected_page_query(_args):
        raise AssertionError('clusterless blocker must run before TLS governance page reads')

    monkeypatch.setattr(tls_routes, 'get_tls_certificate_page', unexpected_page_query)
    response = client.get('/governance/tls-certificates', headers={'HX-Request': 'true'})
    assert response.status_code == 200
    assert 'Connect Your First Kubernetes Cluster' in response.get_data(as_text=True)


def test_tls_sync_status_requires_sync_permission_before_cluster_probe(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(app, monkeypatch, GovernanceRouteUser({'tls_certificates.view'}))

    def unexpected_cluster_probe() -> bool:
        raise AssertionError('cluster readiness must not run before tls_certificates.sync')

    monkeypatch.setattr(tls_routes, 'has_registered_clusters', unexpected_cluster_probe)
    response = client.get('/governance/tls-certificates/sync/job-1/status', headers={'HX-Request': 'true'})
    assert response.status_code == 403


def _committed_tls_snapshot() -> dict[str, str]:
    return {
        'source_label': 'Kubernetes TLS Secrets + Ingresses',
        'status': 'Complete',
        'tone': 'normal',
        'description': 'TLS certificates and Ingress host mappings.',
        'latest_collected': '12 Nov 2026 10:47 WIB',
        'latest_supporting': 'Worker-generated snapshot',
        'scope_label': 'All Clusters',
        'scope_supporting': 'Fleet scope',
        'coverage_label': '11 TLS Secrets',
        'coverage_supporting': 'Collected certificate inventory',
        'coverage_tone': 'normal',
        'exceptions_label': 'No Exceptions',
        'exceptions_supporting': 'No issues detected',
        'exceptions_tone': 'normal',
    }


def test_governance_only_user_cannot_read_or_see_tls_snapshot(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(app, monkeypatch, GovernanceRouteUser({'governance.view'}))

    def unexpected_tls_probe() -> None:
        raise AssertionError('TLS snapshot read or cluster probe must not run without child permission')

    monkeypatch.setattr(governance_routes, 'has_registered_clusters', unexpected_tls_probe)
    monkeypatch.setattr(governance_routes, 'get_tls_collection_snapshot', unexpected_tls_probe)

    response = client.get('/governance/')
    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert 'View Permission Required' in content
    assert 'TLS Collection Snapshot' not in content


def test_governance_authorized_tls_view_reuses_actual_tls_snapshot_partial(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(
        app,
        monkeypatch,
        GovernanceRouteUser({'governance.view', 'tls_certificates.view'}),
    )
    calls: list[str] = []

    monkeypatch.setattr(governance_routes, 'has_registered_clusters', lambda: True)

    def read_snapshot() -> dict[str, str]:
        calls.append('read')
        return _committed_tls_snapshot()

    monkeypatch.setattr(governance_routes, 'get_tls_collection_snapshot', read_snapshot)
    response = client.get('/governance/')

    assert response.status_code == 200
    assert calls == ['read']
    content = response.get_data(as_text=True)
    assert content.count('aria-label="TLS Collection Snapshot"') == 1
    assert 'Kubernetes TLS Secrets + Ingresses' in content
    assert '11 TLS Secrets' in content
    assert 'Governance Control Context' not in content
    assert 'Open TLS Certificates' in content


def test_governance_clusterless_does_not_load_tls_snapshot_even_with_permission(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(
        app,
        monkeypatch,
        GovernanceRouteUser({'governance.view', 'tls_certificates.view'}),
    )
    monkeypatch.setattr(bootstrap_presentation, 'build_cluster_onboarding_context', _clusterless_context)
    monkeypatch.setattr(governance_routes, 'has_registered_clusters', lambda: False)

    def unexpected_tls_query() -> None:
        raise AssertionError('TLS snapshot must not be queried when cluster setup is blocked')

    monkeypatch.setattr(governance_routes, 'get_tls_collection_snapshot', unexpected_tls_query)
    response = client.get('/governance/')

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert 'Connect Your First Kubernetes Cluster' in content
    assert 'TLS Collection Snapshot' not in content


def _internal_pki_source_page() -> dict[str, object]:
    return {
        'registered_total': 1,
        'selected_cluster_id': '',
        'search': '',
        'records': [
            {
                'id': 'cluster-01',
                'name': 'Pilot Cluster',
                'environment': 'non-production',
                'connection_platform': 'kubernetes',
                'connection_version': 'v1.30',
                'collection_status': 'Not Collected',
                'authority_status': 'Not Verified',
                'expiry_status': 'Unknown',
            }
        ],
        'pagination': {
            'page': 1,
            'per_page': 5,
            'allowed_per_page': (5, 10, 25, 50),
            'total_items': 1,
            'total_pages': 1,
            'start_item': 1,
            'end_item': 1,
            'has_prev': False,
            'has_next': False,
            'prev_page': 1,
            'next_page': 1,
        },
    }


def test_internal_pki_source_read_denied_before_registry_probe(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = GovernanceRouteUser({'governance.view', 'clusters.view'})
    client = _client_for_user(app, monkeypatch, user)

    def fail_if_called() -> None:
        raise AssertionError('PKI source registry must not be read without child authorization')

    monkeypatch.setattr(internal_pki_routes, 'has_registered_clusters', fail_if_called)
    monkeypatch.setattr(internal_pki_routes, 'get_internal_certificates_source_page', fail_if_called)
    response = client.get('/governance/internal-certificates')
    assert response.status_code == 403


def test_internal_pki_source_requires_parent_and_cluster_visibility(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for permissions in ({'internal_certificates.view'}, {'governance.view', 'internal_certificates.view'}):
        client = _client_for_user(app, monkeypatch, GovernanceRouteUser(permissions))
        response = client.get('/governance/internal-certificates')
        assert response.status_code == 403


def test_internal_pki_source_workspace_shows_committed_registry_with_unknown_pki(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = GovernanceRouteUser({'governance.view', 'clusters.view', 'internal_certificates.view'})
    client = _client_for_user(app, monkeypatch, user)
    monkeypatch.setattr(internal_pki_routes, 'has_registered_clusters', lambda: True)
    calls: list[str] = []

    def read_committed(_args) -> dict[str, object]:
        calls.append('read')
        return _internal_pki_source_page()

    monkeypatch.setattr(internal_pki_routes, 'get_internal_certificates_source_page', read_committed)
    # This route characterization mocks the source, not a migrated database.
    # The schema blocker must run without querying committed certificate rows.
    monkeypatch.setattr(
        internal_pki_routes,
        'check_internal_pki_schema_readiness',
        lambda: SimpleNamespace(ready=False),
    )

    def must_not_read_inventory(_args) -> None:
        raise AssertionError('The certificate read model must not run when the schema is absent')

    monkeypatch.setattr(internal_pki_routes, 'get_internal_certificate_inventory_page', must_not_read_inventory)
    response = client.get('/governance/internal-certificates')
    assert response.status_code == 200
    assert calls == ['read']
    content = response.get_data(as_text=True)
    assert 'Internal PKI Source Registry' in content
    assert 'Pilot Cluster' in content
    assert 'Not Collected' in content
    assert 'Not Verified' in content
    assert 'Unknown' in content
    assert 'Provider-Owned Renewal' in content
    assert 'Renewal Deferred' not in content
    assert 'Request Renewal' not in content
    assert 'Rotate All' not in content


def test_internal_pki_source_clusterless_blocks_registry_query(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(
        app,
        monkeypatch,
        GovernanceRouteUser({'governance.view', 'clusters.view', 'internal_certificates.view'}),
    )
    monkeypatch.setattr(bootstrap_presentation, 'build_cluster_onboarding_context', _clusterless_context)
    monkeypatch.setattr(internal_pki_routes, 'has_registered_clusters', lambda: False)

    def unexpected_query(_args) -> None:
        raise AssertionError('Registry read must not happen without registered clusters')

    monkeypatch.setattr(internal_pki_routes, 'get_internal_certificates_source_page', unexpected_query)
    response = client.get('/governance/internal-certificates')
    assert response.status_code == 200
    assert 'Connect Your First Kubernetes Cluster' in response.get_data(as_text=True)


def test_internal_pki_committed_inventory_renders_after_readiness_without_live_provider(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    user = GovernanceRouteUser({'governance.view', 'clusters.view', 'internal_certificates.view'})
    client = _client_for_user(app, monkeypatch, user)
    monkeypatch.setattr(internal_pki_routes, 'has_registered_clusters', lambda: True)
    monkeypatch.setattr(
        internal_pki_routes,
        'get_internal_certificates_source_page',
        lambda _args: _internal_pki_source_page(),
    )
    monkeypatch.setattr(
        internal_pki_routes,
        'check_internal_pki_schema_readiness',
        lambda: SimpleNamespace(ready=True),
    )

    def mark_attested(payload: dict) -> None:
        payload['records'][0]['collection_status'] = 'Operator Attested'
        payload['records'][0]['collection_tone'] = 'info'

    monkeypatch.setattr(internal_pki_routes, 'enrich_internal_pki_source_states', mark_attested)
    observed = datetime.now(UTC)
    calls: list[str] = []

    def committed_certificate_page(_args) -> dict:
        calls.append('read')
        return {
            'total': 1,
            'committed_total': 1,
            'records': [
                {
                    'component': 'apiserver',
                    'kind': 'leaf',
                    'cluster_name': 'Pilot Cluster',
                    'node_name': 'control-plane-01',
                    'issuer': 'ca',
                    'externally_managed': False,
                    'not_after': observed + timedelta(days=45),
                    'collected_at': observed,
                    'source_version': 'v1.31.0',
                    'source_kind': 'kubeadm_check_expiration',
                    'coverage': 'partial',
                    'reference': 'CHG-001',
                    'status': 'Outside Window',
                    'tone': 'normal',
                    'freshness': 'Recently Collected',
                    'freshness_tone': 'info',
                }
            ],
            'search': '',
            'cluster_id': '',
            'pagination': {
                'page': 1,
                'per_page': 5,
                'allowed_per_page': (5, 10, 25, 50),
                'total_items': 1,
                'total_pages': 1,
                'start_item': 1,
                'end_item': 1,
                'has_prev': False,
                'has_next': False,
                'prev_page': 1,
                'next_page': 1,
            },
        }

    monkeypatch.setattr(internal_pki_routes, 'get_internal_certificate_inventory_page', committed_certificate_page)
    response = client.get('/governance/internal-certificates')
    assert response.status_code == 200
    assert calls == ['read']
    content = response.get_data(as_text=True)
    assert 'Internal Certificate Registry' in content
    assert 'apiserver' in content
    assert 'control-plane-01' in content
    assert 'Operator Attested' in content
    assert 'Installed status unverified' in content
    assert 'Request Renewal' not in content
    assert 'Rotate All' not in content
    assert 'Provider-Owned Renewal' in content
    assert content.index('data-kaori-capability-navigation') < content.index('Internal Certificates</h1>')


def test_internal_pki_schema_not_ready_never_queries_certificate_rows(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(
        app,
        monkeypatch,
        GovernanceRouteUser({'governance.view', 'clusters.view', 'internal_certificates.view'}),
    )
    monkeypatch.setattr(internal_pki_routes, 'has_registered_clusters', lambda: True)
    monkeypatch.setattr(
        internal_pki_routes,
        'get_internal_certificates_source_page',
        lambda _args: _internal_pki_source_page(),
    )
    monkeypatch.setattr(
        internal_pki_routes,
        'check_internal_pki_schema_readiness',
        lambda: SimpleNamespace(ready=False),
    )

    def must_not_query(_args) -> None:
        raise AssertionError('Missing schema cannot be treated as empty certificate inventory')

    monkeypatch.setattr(internal_pki_routes, 'get_internal_certificate_inventory_page', must_not_query)
    response = client.get('/governance/internal-certificates')
    assert response.status_code == 200
    assert 'Inventory Schema Upgrade Required' in response.get_data(as_text=True)


def test_governance_above_hero_tabs_are_role_aware_and_preserve_cluster_context(app) -> None:
    authorized = GovernanceRouteUser(
        {'governance.view', 'clusters.view', 'tls_certificates.view', 'internal_certificates.view'}
    )
    with app.test_request_context('/governance/internal-certificates?cluster_id=cluster-01'):
        navigation = build_capability_navigation(
            'governance.internal_certificates',
            authorized,
            {'cluster_id': 'cluster-01'},
        )
        assert navigation is not None
        assert navigation['active_key'] == 'internal_certificates'
        assert [tab[1] for tab in navigation['tabs']] == [
            'Overview',
            'TLS Certificates',
            'Internal Certificates',
        ]
        assert all('cluster_id=cluster-01' in tab[4] for tab in navigation['tabs'])

        restricted = GovernanceRouteUser({'governance.view', 'tls_certificates.view'})
        restricted_navigation = build_capability_navigation('governance.overview', restricted)
        assert restricted_navigation is not None
        assert [tab[1] for tab in restricted_navigation['tabs']] == ['Overview', 'TLS Certificates']

        only_parent = GovernanceRouteUser({'governance.view'})
        assert build_capability_navigation('governance.overview', only_parent) is None


def test_governance_internal_pki_registered_cluster_links_preserve_inventory_scope(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(
        app,
        monkeypatch,
        GovernanceRouteUser({'governance.view', 'clusters.view', 'internal_certificates.view'}),
    )
    monkeypatch.setattr(internal_pki_routes, 'has_registered_clusters', lambda: True)
    monkeypatch.setattr(
        internal_pki_routes, 'get_internal_certificates_source_page', lambda _args: _internal_pki_source_page()
    )
    monkeypatch.setattr(
        internal_pki_routes,
        'check_internal_pki_schema_readiness',
        lambda: SimpleNamespace(ready=False),
    )
    response = client.get('/governance/internal-certificates')
    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert 'View PKI Evidence' in content
    assert 'cluster_id=cluster-01' in content
    assert 'Internal Certificate Registry' not in content
    assert 'Inventory Schema Upgrade Required' in content


def test_governance_breadcrumb_reflects_active_internal_certificate_view() -> None:
    """The global navbar must not fall back to TLS for Internal Certificates."""
    cases = (
        ('governance.overview', 'Overview'),
        ('governance.tls_certificates', 'TLS Certificates'),
        ('governance.internal_certificates', 'Internal Certificates'),
    )
    for endpoint, view in cases:
        crumbs = build_navigation_breadcrumb(endpoint, '/governance/internal-certificates')
        assert [item['label'] for item in crumbs] == ['Kubernetes', 'Governance', view]

    unknown = build_navigation_breadcrumb('governance.unknown_view')
    assert unknown[-1]['label'] == 'Overview'

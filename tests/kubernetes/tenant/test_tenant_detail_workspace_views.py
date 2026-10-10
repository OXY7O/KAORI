"""Focused Tenant Details navigation, permissions and state retention (#1069)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from werkzeug.exceptions import NotFound

from app.kubernetes.tenant import route_common


def _prepare(monkeypatch, *, permissions=(), lifecycle='ready',
             provider='native_kubernetes', view=None, payload=None):
    tenant = SimpleNamespace(
        id='t-one', name='tenant-a', ownership_status='adopted',
        lifecycle_status=lifecycle, provider_key=provider,
        provider_state='capsule' if provider == 'capsule' else 'native',
        provider_evidence_json={
            'release_governance': {'release_mode': 'managed_handoff'}
        } if lifecycle == 'released' else {},
    )
    row = {
        'tenant': tenant,
        'capsule_environment_options': ['prod'] if provider == 'capsule' else [],
    }
    scopes = set(permissions)
    monkeypatch.setattr(
        route_common, 'get_tenant_registry_context',
        lambda **kwargs: {'tenant_rows': [row]},
    )
    monkeypatch.setattr(
        route_common, 'current_user',
        SimpleNamespace(has_permission=lambda scope: scope in scopes),
    )
    values = dict(payload or {})
    if view is not None:
        values['view'] = view
    monkeypatch.setattr(
        route_common, 'request',
        SimpleNamespace(values=values),
    )
    monkeypatch.setattr(
        route_common, 'url_for',
        lambda endpoint, **kwargs: (
            '/tenants?section=registry'
            if endpoint == 'tenant.tenants'
            else '/tenant/t-one/manage?view=' + kwargs.get('view', 'overview')
        ),
    )
    return tenant


ADMIN = ('tenant.manage', 'integrations.manage', 'clusters.manage')


def test_ready_platform_admin_has_governed_release_view(monkeypatch):
    _prepare(monkeypatch, permissions=ADMIN, view='release')
    ctx = route_common._tenant_detail_context('t-one')
    keys = [entry[0] for entry in ctx['tenant_detail_tabs']]
    assert keys == ['overview', 'release', 'provider', 'lifecycle']
    assert ctx['active_tenant_detail_view'] == 'release'
    assert ctx['registry_state']['per_page'] == '5'
    assert ctx['tenant_detail_tab_urls']['release'].endswith('view=release')


def test_readonly_viewer_cannot_force_release_by_url(monkeypatch):
    _prepare(monkeypatch, permissions=('tenant.view',), view='release')
    ctx = route_common._tenant_detail_context('t-one')
    assert ctx['active_tenant_detail_view'] == 'overview'
    assert [entry[0] for entry in ctx['tenant_detail_tabs']] == [
        'overview', 'provider', 'lifecycle',
    ]


def test_released_native_requires_separate_governed_handback(monkeypatch):
    _prepare(monkeypatch, permissions=ADMIN, lifecycle='released', view='handback')
    ctx = route_common._tenant_detail_context('t-one')
    assert ctx['active_tenant_detail_view'] == 'handback'
    assert [entry[0] for entry in ctx['tenant_detail_tabs']] == [
        'overview', 'handback', 'provider', 'lifecycle',
    ]


def test_capsule_attachment_remains_provider_scoped(monkeypatch):
    _prepare(monkeypatch, permissions=('tenant.manage',), provider='capsule',
             view='attachment')
    ctx = route_common._tenant_detail_context('t-one')
    assert ctx['active_tenant_detail_view'] == 'attachment'
    assert 'release' not in [entry[0] for entry in ctx['tenant_detail_tabs']]


def test_invalid_or_replaced_workflow_uses_safe_overview(monkeypatch):
    _prepare(monkeypatch, permissions=ADMIN, lifecycle='released', view='release')
    assert route_common._tenant_detail_context('t-one')['active_tenant_detail_view'] == 'overview'


def test_form_view_is_retained_across_post_like_request(monkeypatch):
    _prepare(monkeypatch, permissions=ADMIN, payload={
        'tenant_detail_view': 'release',
        'registry_page': '4', 'registry_search': 'payments',
        'registry_per_page': '5',
    })
    ctx = route_common._tenant_detail_context('t-one')
    assert ctx['active_tenant_detail_view'] == 'release'
    assert ctx['registry_state']['page'] == '4'
    assert ctx['registry_state']['search'] == 'payments'


def test_missing_tenant_is_a_not_found_response(monkeypatch):
    monkeypatch.setattr(
        route_common, 'get_tenant_registry_context',
        lambda **kwargs: {'tenant_rows': []},
    )
    with pytest.raises(NotFound):
        route_common._tenant_detail_context('missing')

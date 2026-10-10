"""Tenant Management accordion state is authorized and survives HTMX refresh.

No Kubernetes read or write is permitted during normal Tenant detail GET.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from werkzeug.exceptions import NotFound

from app.kubernetes.tenant import route_common


ADMIN = {'tenant.manage', 'integrations.manage', 'clusters.manage'}


def _context(monkeypatch, *, perms=ADMIN, lifecycle='ready', provider='native_kubernetes',
             selected='', evidence=None):
    tenant = SimpleNamespace(
        id='tenant-a', name='tenant-a', ownership_status='adopted',
        lifecycle_status=lifecycle, provider_key=provider,
        provider_state='capsule' if provider == 'capsule' else 'native',
        provider_evidence_json=evidence or {},
    )
    row = {'tenant': tenant, 'capsule_environment_options': ['development']}
    monkeypatch.setattr(
        route_common, 'get_tenant_registry_context',
        lambda **_kwargs: {'tenant_rows': [row]},
    )
    monkeypatch.setattr(
        route_common, 'current_user',
        SimpleNamespace(has_permission=lambda code: code in perms),
    )
    monkeypatch.setattr(
        route_common, 'request',
        SimpleNamespace(values={'tenant_detail_section': selected}),
    )
    monkeypatch.setattr(
        route_common, 'url_for',
        lambda endpoint, **_kwargs: '/tenants?section=registry' if endpoint == 'tenant.tenants'
        else '/tenants/tenant-a/manage',
    )
    return route_common._tenant_detail_context('tenant-a')


def test_ready_platform_admin_defaults_to_release_open(monkeypatch):
    context = _context(monkeypatch)
    assert context['tenant_detail_open_section'] == 'release'


def test_post_keeps_current_governed_release_section(monkeypatch):
    context = _context(monkeypatch, selected='release')
    assert context['tenant_detail_open_section'] == 'release'


def test_readonly_viewer_does_not_open_release(monkeypatch):
    context = _context(monkeypatch, perms={'tenant.view'}, selected='release')
    assert context['tenant_detail_open_section'] == 'provider'


def test_released_generation_switches_to_handback_only_if_authorized(monkeypatch):
    evidence = {'release_governance': {'release_mode': 'managed_handoff'}}
    context = _context(
        monkeypatch, lifecycle='released', selected='release', evidence=evidence,
    )
    assert context['tenant_detail_open_section'] == 'handback'
    context = _context(
        monkeypatch, lifecycle='released', selected='handback', evidence=evidence,
        perms={'tenant.view'},
    )
    assert context['tenant_detail_open_section'] == 'provider'


def test_capsule_attachment_reopens_only_when_valid(monkeypatch):
    ctx = _context(
        monkeypatch, perms={'tenant.manage'}, provider='capsule', selected='attachment',
    )
    assert ctx['tenant_detail_open_section'] == 'attachment'
    ctx = _context(monkeypatch, perms={'tenant.view'}, provider='capsule', selected='attachment')
    assert ctx['tenant_detail_open_section'] == 'provider'


def test_lifecycle_panel_retained_after_decommission_post(monkeypatch):
    ctx = _context(monkeypatch, lifecycle='decommissioning', selected='lifecycle')
    assert ctx['tenant_detail_open_section'] == 'lifecycle'


def test_unknown_section_never_enters_template(monkeypatch):
    ctx = _context(monkeypatch, selected='<script>malicious</script>')
    assert ctx['tenant_detail_open_section'] == 'release'


def test_missing_tenant_returns_404(monkeypatch):
    monkeypatch.setattr(
        route_common, 'get_tenant_registry_context',
        lambda **_kwargs: {'tenant_rows': []},
    )
    with pytest.raises(NotFound):
        route_common._tenant_detail_context('missing')

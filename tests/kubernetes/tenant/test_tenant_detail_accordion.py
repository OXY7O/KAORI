"""Other Tenant governance panels remain scoped; Release itself is always visible.

No Kubernetes read or write is permitted during normal Tenant detail GET.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from werkzeug.exceptions import NotFound

from app.kubernetes.tenant import route_common


ADMIN = {'tenant.manage', 'integrations.manage', 'clusters.manage'}


def _context(monkeypatch, *, perms=ADMIN, lifecycle='ready', provider='native_kubernetes',
             selected='', evidence=None, release_step='', submitted_step=''):
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
        SimpleNamespace(values={
            'tenant_detail_section': selected,
            'release_step': release_step,
            'tenant_release_step': submitted_step,
        }),
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
    assert context['tenant_release_step'] == 'scope'




def test_release_wizard_accepts_bounded_url_step(monkeypatch):
    ctx = _context(monkeypatch, selected='release', release_step='approval')
    assert ctx['tenant_detail_open_section'] == 'release'
    assert ctx['tenant_release_step'] == 'approval'
    assert list(ctx['tenant_release_step_urls']) == [
        'scope', 'handoff', 'approval', 'finalize',
    ]


def test_governance_post_keeps_selected_wizard_step(monkeypatch):
    ctx = _context(
        monkeypatch, selected='release', submitted_step='finalize',
    )
    assert ctx['tenant_detail_open_section'] == 'release'
    assert ctx['tenant_release_step'] == 'finalize'


def test_invalid_step_falls_back_to_scope_without_authorizing_release(monkeypatch):
    ctx = _context(
        monkeypatch, selected='release', release_step='<script>',
    )
    assert ctx['tenant_release_step'] == 'scope'


def test_form_step_has_priority_over_old_url_for_htmx_response(monkeypatch):
    ctx = _context(
        monkeypatch, selected='release', release_step='scope',
        submitted_step='handoff',
    )
    assert ctx['tenant_release_step'] == 'handoff'


def test_post_keeps_current_governed_release_section(monkeypatch):
    context = _context(monkeypatch, selected='release')
    assert context['tenant_detail_open_section'] == 'release'
    assert context['tenant_release_step'] == 'scope'


def test_readonly_viewer_does_not_open_release(monkeypatch):
    context = _context(monkeypatch, perms={'tenant.view'}, selected='release')
    assert context['tenant_detail_open_section'] == 'provider'
    assert context['tenant_release_step'] == 'scope'


def test_released_generation_switches_to_handback_only_if_authorized(monkeypatch):
    evidence = {'release_governance': {'release_mode': 'managed_handoff'}}
    context = _context(
        monkeypatch, lifecycle='released', selected='release', evidence=evidence,
    )
    assert context['tenant_detail_open_section'] == 'handback'
    assert context['tenant_release_step'] == 'scope'
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


def test_release_wizard_explains_platform_admin_ownership_without_bypassing_approval() -> None:
    """#1183: Step 3/4 show the next safe actor/action instead of generic 2/5."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    template = (
        root / 'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html'
    ).read_text(encoding='utf-8')
    assert 'aria-label="Independent Platform Admin required"' in template
    assert 'handoff_plan.requested_by == current_user.id' in template
    assert 'Another authorized Platform Admin must verify provider identity' in template
    assert 'not native_cycle.verified_successor_acceptance' in template
    assert 'not native_cycle.provider_transfer_verified' in template
    assert 'Verify Provider &amp; Accept as Platform Admin' in template
    assert 'Execute Native Handoff' in template
    assert 'Dry-run and external references are not consent.' in template
    assert 'a new-generation Re-adopt is a separate governed action' in template
    assert "row.native_release_readiness.approval_complete" in template
    assert 'tenant_release_step_urls[\'approval\']' in template
    assert "hx-post=\"{{ url_for('tenant.accept_native_successor_handoff_route'" in template
    assert "hx-post=\"{{ url_for('tenant.execute_native_release_handoff_route'" in template

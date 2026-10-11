"""Source/UI contract #1132: Native residual recovery through Tenant Detail → Discovery.

These contracts are authored while CI/CD and runtime provider mutation HOLD.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
DETAIL = ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html'
PARTIAL = ROOT / 'app/templates/kubernetes/tenant/partials/_native_residual_recovery.html'
ROUTES = ROOT / 'app/kubernetes/tenant/routes.py'
REGISTRY = ROOT / 'app/kubernetes/tenant/registry_context.py'
DISCOVERY = ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_discovery.html'


def source(path):
    return path.read_text(encoding='utf-8')


def test_recovery_is_scoped_to_verified_native_handback_in_tenant_detail():
    detail, partial = source(DETAIL), source(PARTIAL)
    Environment().parse(detail)
    Environment().parse(partial)
    assert "tenant.provider_key == 'native_kubernetes' and tenant.lifecycle_status == 'released'" in detail
    assert "handback_receipt and handback_receipt.status == 'verified'" in partial
    assert "partials/_native_residual_recovery.html" in detail
    assert 'id="tenant-native-residual-recovery"' in partial
    assert 'name="tenant-governance"' in detail
    assert 'tenant_detail_open_section == \'handback\'' in detail
    assert "'Handback Verified' if handback_receipt" in detail
    assert 'Recovery Verified' in partial
    assert 'Recovery Review Required' in partial
    assert 'Pending Independent Review' in partial
    assert 'Recovery Check · If Blocked' in partial
    assert 'Check Discovery First' in partial
    assert 'If your Namespace is already eligible' in partial


def test_recovery_forms_use_existing_htmx_csrf_loading_and_independent_actor_guard():
    partial = source(PARTIAL)
    for route in (
        'assess_native_residual_cleanup_route',
        'prepare_native_residual_cleanup_route',
        'approve_native_residual_cleanup_route',
        'execute_native_residual_cleanup_route',
    ):
        assert f"tenant.{route}" in partial
    assert partial.count('name="csrf_token"') == 4
    assert partial.count('hx-target="#tenant-management-detail"') == 4
    assert partial.count('hx-select="#tenant-management-detail"') == 4
    assert partial.count('hx-indicator="#tenant-management-loading"') == 4
    assert partial.count('hx-disabled-elt="find button[type=\'submit\']"') == 4
    assert partial.count('name="tenant_detail_section" value="handback"') == 4
    assert partial.count('name="tenant_detail_id"') == 4
    assert 'name="plan_sha256" value="{{ recovery_plan.plan_sha256 }}"' in partial
    assert "recovery_plan.requested_by != current_user.id" in partial
    assert "recovery_approval.approved_by == current_user.id" in partial
    assert "row.native_residual_plan_current" in partial
    assert "row.native_residual_approval_current" in partial
    assert 'name="change_reference"' in partial
    assert 'confirm_native_residual_execute' in partial
    assert 'required' in partial
    assert 'min-h-10' in partial
    assert 'focus-visible:ring-2' in partial


def test_ordinary_tenant_get_only_reads_committed_projected_recovery_receipts():
    registry = source(REGISTRY)
    assert 'kubernetes_tenant_native_residual_cleanup_plan' in registry
    assert 'kubernetes_tenant_native_residual_cleanup_approval' in registry
    assert 'kubernetes_tenant_native_residual_cleanup_execution' in registry
    assert 'native_residual_plan_current' in registry
    assert 'native_residual_approval_current' in registry
    assert 'assess_legacy_native_profile_residue_readonly(' not in registry
    assert 'execute_native_residual_cleanup_committed(' not in registry
    assert 'runtime_adapter.' not in registry


def test_verified_cleanup_handoff_is_navigation_not_automatic_adopt():
    partial, routes, discovery = source(PARTIAL), source(ROUTES), source(DISCOVERY)
    assert "url_for('tenant.tenants', section='discovery')" in partial
    assert "Open Discovery &amp; Review Adoption" in partial
    assert 'This link does not adopt automatically' in partial
    assert 'Review Adoption' in discovery
    assert 'adopt_discovered_tenant_committed' in routes
    assert 'adopt_discovered_tenant_committed(' not in partial
    assert "if recovery_verified" in partial
    assert "if recovery_execution" in partial
    assert 'No retry or automatic cleanup is available' in partial


def test_route_blocks_unknown_mutation_result_and_keeps_audit_feedback():
    routes = source(ROUTES)
    block = routes.split('def execute_native_residual_cleanup_route(', 1)[1].split(
        "@tenant_bp.post('/tenants/<string:tenant_id>/decommission')", 1
    )[0]
    assert 'execute_native_residual_cleanup_committed(' in block
    assert 'confirmed=request.form.get(\'confirm_native_residual_execute\') == \'execute\'' in block
    assert 'except Exception:' in block
    assert 'Provider Recovery Needs Manual Review' in block
    assert 'Do not retry, manually delete labels, or force Re-adopt' in block
    assert '_tenant_section_redirect(\'registry\')' in block
    assert 'tenant.release.native_residual_cleanup_verified' not in block

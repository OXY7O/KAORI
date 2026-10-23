"""Source/UI contract #1132: Native residual recovery through Tenant Detail → Discovery.

These contracts are authored while CI/CD and runtime provider mutation HOLD.
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
DETAIL = ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html'
PARTIAL = ROOT / 'app/templates/kubernetes/tenant/partials/_native_residual_recovery.html'
ROUTES = ROOT / 'app/kubernetes/tenant/routes.py'
REGISTRY = ROOT / 'app/kubernetes/tenant/registry_context.py'
DISCOVERY = ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_discovery.html'

PLAN_SHA_HIDDEN_INPUT = re.compile(
    r'<input\s+type="hidden"\s+name="plan_sha256"\s+value="\{\{ recovery_plan\.plan_sha256 \}\}"'
)


def source(path):
    return path.read_text(encoding='utf-8')


def test_recovery_is_scoped_to_verified_native_handback_in_tenant_detail():
    detail, partial = source(DETAIL), source(PARTIAL)
    Environment().parse(detail)
    Environment().parse(partial)
    assert "tenant.provider_key == 'native_kubernetes' and tenant.lifecycle_status == 'released'" in detail
    assert "handback_receipt and handback_receipt.status == 'verified'" in partial
    assert 'partials/_native_residual_recovery.html' in detail
    assert 'id="tenant-native-residual-recovery"' in partial
    assert 'name="tenant-governance"' in detail
    assert "tenant_detail_open_section == 'handback'" in detail
    assert "'Handback Verified' if handback_receipt" in detail
    assert 'Recovery Verified' in partial
    assert 'Recovery Review Required' in partial
    assert 'Pending Independent Review' in partial
    assert 'Recovery Check · If Blocked' in partial
    assert 'Check Discovery First' in partial
    assert 'If eligible, use Review Adoption.' in partial


def test_recovery_forms_use_existing_htmx_csrf_loading_and_independent_actor_guard():
    partial = source(PARTIAL)
    for route in (
        'assess_native_residual_cleanup_route',
        'prepare_native_residual_cleanup_route',
        'approve_native_residual_cleanup_route',
        'execute_native_residual_cleanup_route',
    ):
        assert f'tenant.{route}' in partial
    assert partial.count('name="csrf_token"') == 4
    assert partial.count('hx-target="#tenant-management-detail"') == 4
    assert partial.count('hx-select="#tenant-management-detail"') == 4
    assert partial.count('hx-indicator="#tenant-management-loading"') == 4
    assert partial.count('hx-disabled-elt="find button[type=\'submit\']"') == 4
    assert partial.count('name="tenant_detail_section" value="handback"') == 4
    assert partial.count('name="tenant_detail_id"') == 4
    assert PLAN_SHA_HIDDEN_INPUT.search(partial)
    assert 'recovery_plan.requested_by != current_user.id' in partial
    assert 'recovery_approval.approved_by == current_user.id' in partial
    assert 'row.native_residual_plan_current' in partial
    assert 'row.native_residual_approval_current' in partial
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
    assert 'Open Discovery &amp; Review Adoption' in partial
    assert 'This link does not adopt automatically' in partial
    assert 'Review Adoption' in discovery
    assert 'adopt_discovered_tenant_committed' in routes
    assert 'adopt_discovered_tenant_committed(' not in partial
    assert 'if recovery_verified' in partial
    assert 'if recovery_execution' in partial
    assert 'No retry or automatic cleanup is available' in partial


def test_route_blocks_unknown_mutation_result_and_keeps_audit_feedback():
    routes = source(ROUTES)
    block = routes.split('def execute_native_residual_cleanup_route(', 1)[1].split(
        "@tenant_bp.post('/tenants/<string:tenant_id>/decommission')", 1
    )[0]
    assert 'execute_native_residual_cleanup_committed(' in block
    assert "confirmed=request.form.get('confirm_native_residual_execute') == 'execute'" in block
    assert 'except Exception:' in block
    assert 'Provider Recovery Needs Manual Review' in block
    assert 'Do not retry, manually delete labels, or force Re-adopt' in block
    assert "_tenant_section_redirect('registry')" in block
    assert 'tenant.release.native_residual_cleanup_verified' not in block


def test_recovery_redesign_uses_readable_steps_and_distinct_assessment_plan_sections():
    """#1188: visual hierarchy must not imply completed recovery or add provider actions."""
    partial = source(PARTIAL)
    Environment().parse(partial)
    assert 'tenant-native-residual-recovery-heading' in partial
    assert 'text-base font-semibold leading-6' in partial
    assert '<header class="flex min-w-0 flex-wrap' in partial
    assert '<ol class="grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-4"' in partial
    assert 'Governed recovery stages' in partial
    assert 'These describe governance stages, not checkmarks or proof of progress.' in partial
    assert 'loop.index' in partial
    assert 'aria-labelledby="tenant-recovery-discovery-guidance"' in partial
    assert 'aria-labelledby="tenant-recovery-assessment-heading"' in partial
    assert 'aria-labelledby="tenant-recovery-prepare-heading"' in partial
    assert 'Assessment Actions' in partial
    assert 'Prepare Recovery Plan' in partial
    assert 'sm:grid-cols-2' in partial
    assert 'data-native-residual-prepare-form' in partial
    assert 'data-native-residual-recovery-workspace' in partial
    assert 'hover:bg-kaori-soft/30' in partial
    assert 'bg-kaori-primary' in partial
    assert 'No retry or automatic cleanup is available' in partial
    assert 'only rendered' not in partial  # No invented mutation capability.
    assert partial.count('name="csrf_token"') == 4
    assert partial.count('type="submit"') == 4
    assert partial.count("href=\"{{ url_for('tenant.tenants', section='discovery') }}\"") == 2


def test_recovery_redesign_preserves_distinct_sensitive_workflow_forms():
    partial = source(PARTIAL)
    for route in (
        'assess_native_residual_cleanup_route',
        'prepare_native_residual_cleanup_route',
        'approve_native_residual_cleanup_route',
        'execute_native_residual_cleanup_route',
    ):
        assert partial.count('action="{{ url_for(\'tenant.' + route) == 1
        assert partial.count('hx-post="{{ url_for(\'tenant.' + route) == 1
    assert partial.count('name="confirm_native_residual_prepare"') == 1
    assert partial.count('name="confirm_native_residual_approval"') == 1
    assert partial.count('name="confirm_native_residual_execute"') == 1
    assert len(PLAN_SHA_HIDDEN_INPUT.findall(partial)) == 2
    assert 'recovery_approval.approved_by == current_user.id' in partial
    assert 'recovery_plan.requested_by != current_user.id' in partial
    assert 'row.native_residual_plan_current' in partial
    assert 'row.native_residual_approval_current' in partial
    assert 'if recovery_execution' in partial
    assert 'if recovery_verified' in partial
    assert 'This link does not adopt automatically.' in partial


def test_recovery_prepare_form_is_compact_with_unchanged_governed_inputs():
    partial = source(PARTIAL)
    detail = source(DETAIL)
    Environment().parse(partial)
    Environment().parse(detail)
    form = next(
        item for item in re.findall(r'<form\b.*?</form>', partial, flags=re.DOTALL)
        if 'data-native-residual-prepare-form' in item
    )
    assert 'max-w-2xl' not in form
    assert 'items-start gap-3' in form
    assert 'name="change_reference"' in form
    assert 'minlength="3"' in form and 'maxlength="120"' in form
    assert 'name="confirm_native_residual_prepare"' in form
    assert re.search(r'name="confirm_native_residual_prepare"\s+value="prepare"\s+required', form)
    assert 'name="csrf_token"' in form and 'hx-post=' in form
    assert 'no Kubernetes changes.' in form
    assert 'Prepare Recovery Plan' in form
    assert 'Prepare Governed Recovery Plan' not in form
    assert 'Different Admin reviews the exact plan SHA' in partial
    assert 'Label-only PATCH with verified read-back' in partial
    assert 'Check fresh Discovery first. If eligible, use Review Adoption.' in partial
    assert 'recovery_plan.requested_by != current_user.id' in partial
    assert 'row.native_residual_approval_current' in partial
    assert partial.count('name="csrf_token"') == 4


def test_native_handback_title_uses_existing_kaori_guide_without_extra_provider_action():
    detail = source(DETAIL)
    handback = detail.split('id="tenant-native-handback"', 1)[1].split(
        'id="tenant-capsule-handback"', 1
    )[0]
    assert handback.count("info_tip.render('tenant-native-platform-handback-guide'") == 1
    assert "'Platform Admin Handback & Re-adopt'" in handback
    assert "variant='guide'" in handback
    assert 'Fresh Discovery and explicit Review Adoption are separate from handback.' in handback
    assert "tenant.verify_native_successor_handback_route" in handback
    assert handback.count('name="confirm_successor_handback"') == 1
    assert 'name="release_plan_sha256"' in handback
    assert detail.count('<form method="post"') == 23


def test_residual_recovery_uses_balanced_assessment_and_plan_columns():
    partial = source(PARTIAL)
    Environment().parse(partial)
    assert partial.count('data-native-residual-recovery-workspace') == 1
    workspace = partial.split('data-native-residual-recovery-workspace', 1)[1].split(
        '        {% endif %}', 1
    )[0]
    assert 'lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]' in partial
    assert 'aria-labelledby="tenant-recovery-assessment-heading"' in workspace
    assert 'aria-labelledby="tenant-recovery-prepare-heading"' in workspace
    assert 'lg:border-r lg:border-outline-subtle' in workspace
    assert 'border-t border-outline-subtle p-4 lg:border-t-0' in workspace
    assert 'mt-3 grid min-w-0 gap-2"' in workspace
    assert 'mt-3 grid min-w-0 gap-2 sm:grid-cols-2' not in workspace
    assert 'max-w-2xl' not in workspace
    assert 'Check Discovery First' in workspace
    assert 'Assess Live Provider Residue (Read-only)' in workspace
    assert 'Prepare Recovery Plan' in workspace
    assert workspace.count('<section ') == 2
    assert workspace.count('</section>') == 2
    assert 'data-native-residual-prepare-form' in workspace
    assert 'minlength="3"' in workspace and 'maxlength="120"' in workspace
    assert 'name="confirm_native_residual_prepare"' in workspace
    assert 'value="prepare"' in workspace
    assert 'required' in workspace
    assert workspace.count('name="csrf_token"') == 2
    assert workspace.count('hx-post=') == 2
    assert partial.count('name="csrf_token"') == 4
    assert partial.count('type="submit"') == 4

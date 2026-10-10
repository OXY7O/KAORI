"""Tenant Registry links to a dedicated, committed-only governance page (#1065).

This replaces the superseded native Tenant Management dialog contract #1022.
Provider mutation/authorization remains owned by existing Tenant services.
"""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


REGISTRY = 'app/templates/kubernetes/tenant/partials/_tenant_registry.html'
DETAIL = 'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html'
PAGE = 'app/templates/kubernetes/tenant/tenant_detail.html'


def test_compact_registry_has_one_full_page_detail_link_not_a_management_dialog():
    registry = read(REGISTRY)
    actions = registry.split(
        '<td class="{{ table_ui.cell_classes(action=true) }} align-middle">', 1,
    )[1].split('</td>', 1)[0]
    assert actions.count('<a ') == 1
    assert 'tenant.tenant_detail' in actions
    assert 'hx-boost="false"' in actions
    assert 'tenant_id=tenant.id' in actions
    assert 'table_ui.action_classes()' in actions
    assert "'Manage' if can_manage else 'View'" in actions
    for key in ('page', 'per_page', 'search', 'cluster_id', 'environment', 'lifecycle_status'):
        assert f'registry_{key}=' in actions
    assert 'data-kaori-dialog-open' not in registry
    assert 'data-tenant-registry-actions-dialog' not in registry
    assert '<dialog' not in registry
    assert 'Review Release' not in registry
    assert 'Decommission' not in actions
    assert 'registry_ui.footer(' in registry


def test_detail_page_uses_approved_tenant_shell_and_return_breadcrumb():
    page = read(PAGE)
    detail = read(DETAIL)
    assert '{% extends "kubernetes/tenant/base.html" %}' in page
    assert 'aria-label="Tenant breadcrumbs"' in page
    assert 'aria-current="page"' in page
    assert 'return_to_registry_url' in page
    assert 'partials/_tenant_management_detail.html' in page
    assert 'id="tenant-management-detail"' in detail
    assert 'data-tenant-management-detail="{{ tenant.id }}"' in detail
    assert 'Back to Tenant Registry' in detail
    assert 'Back to Registry' in detail
    assert 'grid grid-cols-3 divide-x' in detail
    assert 'aria-label="Tenant management sections"' in detail
    assert 'overflow-y-auto bg-surface-page' not in detail
    assert 'max-h-[calc(100dvh-2rem)]' not in detail
    assert 'data-kaori-native-dialog' not in detail
    assert 'data-kaori-dialog-auto-open' not in detail
    assert 'data-kaori-dialog-preserve-on-swap' not in detail


def test_detail_route_reads_one_exact_tenant_without_live_provider_or_filter_leak():
    routes = read('app/kubernetes/tenant/routes.py')
    common = read('app/kubernetes/tenant/route_common.py')
    context = read('app/kubernetes/tenant/registry_context.py')
    assert "@tenant_bp.get('/tenants/<string:tenant_id>/manage')" in routes
    assert "@any_permission_required('tenant.view', 'tenant.manage')" in routes
    assert "def tenant_detail(tenant_id: str):" in routes
    assert "_tenant_detail_context(tenant_id)" in routes
    assert "get_tenant_registry_context(tenant_id=tenant_id, per_page=1)" in common
    assert "if not rows:" in common
    assert "abort(404)" in common
    assert "query.filter(Tenant.id == tenant_id)" in context
    assert "include_decommission_preflight: bool = True" in context
    assert "runtime_adapter.build_client(" not in common
    assert "runtime_adapter.build_client(" not in context


def test_mutation_forms_refresh_selected_detail_and_deliver_normal_toast_oob():
    detail = read(DETAIL)
    common = read('app/kubernetes/tenant/route_common.py')
    toast = read('app/templates/components/operational_toast.html')
    assert detail.count('<form ') == 14
    assert detail.count('name="csrf_token"') == 14
    assert detail.count('name="tenant_detail_id"') == 14
    assert detail.count('registry_state.items()') == 14
    assert detail.count('hx-target="#tenant-management-detail"') == 14
    assert detail.count('hx-select="#tenant-management-detail"') == 14
    assert detail.count('hx-post=') == 14
    assert "detail_id = str(request.form.get('tenant_detail_id')" in common
    assert "'kubernetes/tenant/partials/_tenant_management_detail.html'" in common
    assert "'tenant.tenant_detail', tenant_id=detail_id" in common
    assert "toast_oob=True" in common
    assert 'beforeend:#operational-toast-stack' in toast
    assert 'data-kaori-native-dialog' not in detail
    assert "htmx:beforeSwap" not in detail


def test_detail_keeps_governed_workflows_without_reimplementing_endpoints():
    detail = read(DETAIL)
    for name in (
        'review_tenant_release_route',
        'prepare_tenant_release_handoff_route',
        'restart_expired_tenant_release_handoff_route',
        'approve_tenant_release_handoff_route',
        'record_tenant_release_successor_reference_route',
        'accept_native_successor_handoff_route',
        'dry_run_native_release_handoff_route',
        'execute_native_release_handoff_route',
        'inspect_native_external_handoff_route',
        'release_tenant_governance_route',
        'finalize_verified_native_release_route',
        'verify_native_successor_handback_route',
        'attach_existing_capsule_namespace_route',
        'decommission_tenant_route',
    ):
        assert name in detail
    sections = (
        'aria-label="Release governance"',
        'aria-label="Namespace attachment"',
        'aria-label="Provider authority"',
        'aria-label="Tenant lifecycle actions"',
    )
    assert all(section in detail for section in sections)
    assert [detail.index(section) for section in sections] == sorted(
        detail.index(section) for section in sections
    )
    assert 'data-release-handoff-approval' in detail
    assert 'Acknowledge as Independent Reviewer' in detail
    assert 'handoff_plan.requested_by != current_user.id' in detail
    assert 'row.release_preflight.blockers' in detail
    assert 'data-capsule-namespace-attach' in detail
    assert 'name="namespace_uid"' in detail
    assert 'name="namespace_resource_version"' in detail


def test_decommission_keeps_dedicated_short_confirmation_modal():
    detail = read(DETAIL)
    assert "destructive_modal.render('tenant-decommission-modal'" in detail
    assert 'data-destructive-modal-open' in detail
    assert 'data-destructive-submit-button-id=' in detail
    assert 'name="csrf_token"' in detail
    assert 'name="tenant_detail_id"' in detail
    assert '<dialog' not in detail
    assert 'data-kaori-dialog-close' not in detail


def test_detail_is_read_only_for_nonmanagers_and_no_secret_bearers():
    detail = read(DETAIL)
    assert 'if not can_manage' in detail
    assert "can_manage and current_user.has_permission('integrations.manage')" in detail
    assert "current_user.has_permission('clusters.manage')" in detail
    assert 'name="kubernetes_successor_token"' not in detail
    assert 'client-key-data' not in detail
    assert 'private_key' not in detail
    assert 'csrf_token()' in detail


def test_tenant_detail_templates_parse_under_real_jinja_parser():
    env = Environment(autoescape=True)
    for path in (REGISTRY, PAGE, DETAIL):
        env.parse(read(path))

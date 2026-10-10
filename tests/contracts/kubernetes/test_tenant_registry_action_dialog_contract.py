"""Tenant Registry manages one selected Tenant in a persistent inline workspace.

This is a UI contract: authorization, provider read-back and audit remain owned
by existing KAORI Tenant services.
"""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "app/templates/kubernetes/tenant/partials/_tenant_registry.html"


def _template() -> str:
    return REGISTRY.read_text(encoding="utf-8")


def _panel() -> str:
    return _template().split("data-tenant-registry-management-panel", 1)[1]


def test_registry_row_has_single_accessible_manage_link() -> None:
    source = _template()
    actions = source.split('<td class="{{ table_ui.cell_classes(action=true) }} align-middle">', 1)[1]
    actions = actions.split("</td>", 1)[0]

    assert actions.count("<a ") == 1
    assert "<button" not in actions
    assert "tenant_management_url" in actions
    assert 'hx-get="{{ tenant_management_url }}"' in actions
    assert 'hx-target="#tenant-admin-workspace"' in actions
    assert 'hx-select="#tenant-admin-workspace"' in actions
    assert 'hx-push-url="true"' in actions
    assert 'aria-expanded=' in actions
    assert 'aria-controls="tenant-registry-management-panel"' in actions
    assert "table_ui.action_classes()" in actions
    assert "'Manage' if can_manage else 'View'" in actions
    assert "Review Release" not in actions
    assert "Decommission" not in actions


def test_only_one_full_width_panel_is_selected_outside_table() -> None:
    source = _template()
    panel = _panel()

    assert source.index('id="tenant-registry-management-panel"') > source.index("registry_ui.footer(")
    assert source.count("data-tenant-registry-management-panel") == 1
    assert "{% if managed_tenant_id == tenant.id|string %}" in source
    assert "data-kaori-native-dialog" not in source
    assert 'data-kaori-dialog-open' not in source
    assert 'data-kaori-dialog-close' not in source
    assert 'class="mt-4 min-w-0 overflow-hidden rounded-xl' in panel
    assert "max-h-[calc(100dvh-2rem)]" not in panel
    assert "lg:grid-cols-3" not in panel
    assert "<aside " not in panel
    assert 'aria-labelledby=' in panel
    assert 'aria-describedby=' in panel
    assert 'aria-label="Tenant management sections"' in panel
    assert 'grid grid-cols-3 divide-x' in panel
    assert 'tenant_management_close_url' in panel
    assert panel.count('hx-get="{{ tenant_management_close_url }}"') == 2
    assert 'aria-label="Close management panel' in panel
    for label in (
        "Namespaces", "Environments", "Lifecycle", "Provider Authority",
        "Namespace Attachment", "Release Governance", "Lifecycle Actions",
    ):
        assert label in panel


def test_write_actions_and_provider_safety_boundaries_are_unchanged() -> None:
    panel = _panel()
    source = _template()

    assert "can_manage and tenant.provider_key == 'capsule'" in panel
    assert "tenant.ownership_status == 'adopted'" in panel
    assert "current_user.has_permission('integrations.manage')" in panel
    assert "if not can_manage" in panel
    assert panel.count('hx-target="#tenant-admin-workspace"') == 11
    assert panel.count("hx-post=") == 9
    assert panel.count('name="csrf_token"') == 9
    for route in (
        "review_tenant_release_route",
        "prepare_tenant_release_handoff_route",
        "record_tenant_release_successor_reference_route",
        "dry_run_native_release_handoff_route",
        "inspect_native_external_handoff_route",
        "approve_tenant_release_handoff_route",
        "release_tenant_governance_route",
        "decommission_tenant_route",
    ):
        assert route in panel
    assert 'name="confirm_release_governance"' in panel
    assert 'name="confirm_handoff_approval"' in panel
    assert 'name="namespace_uid"' in panel
    assert 'name="namespace_resource_version"' in panel
    assert 'data-capsule-namespace-attach' in panel
    assert 'data-destructive-modal-open' in panel
    assert 'data-destructive-submit-button-id=' in panel
    assert "destructive_modal.render('tenant-decommission-modal'" in source


def test_release_readiness_remains_visible_and_workflow_ordered() -> None:
    panel = _panel()
    release = panel.split('aria-label="Release governance"', 1)[1].split(
        'aria-label="Namespace attachment"', 1
    )[0]
    stages = (
        'aria-label="Release readiness"',
        'aria-label="Provider handoff inventory"',
        'aria-label="Governed handoff workflow"',
        'aria-label="Independent verification and release"',
    )
    assert all(stage in release for stage in stages)
    assert [release.index(stage) for stage in stages] == sorted(
        release.index(stage) for stage in stages
    )
    readiness = release.split(stages[0], 1)[1].split(stages[1], 1)[0]
    inventory = release.split(stages[1], 1)[1].split(stages[2], 1)[0]
    handoff = release.split(stages[2], 1)[1].split(stages[3], 1)[0]
    final = release.split(stages[3], 1)[1]
    assert 'review_tenant_release_route' in readiness
    assert 'Latest Release Review' in readiness
    assert 'Release blockers' in readiness
    assert 'row.release_preflight.blockers' in readiness
    assert 'bg-status-warning-soft p-4' in readiness
    assert 'row.release_preflight.handoff_components' in inventory
    assert 'Handoff inventory is read-only provider evidence' in inventory
    assert 'hx-post=' not in inventory
    assert '<details' not in inventory
    assert 'data-release-handoff-approval' in handoff
    assert "handoff_plan.requested_by != current_user.id" in handoff
    assert "handoff_approval.approved_by != current_user.id" in handoff
    assert "row.release_native_handoff_dry_run.status == 'dry_run_passed'" in handoff
    assert 'name="confirm_handoff_approval"' in handoff
    assert 'release_tenant_governance_route' in final
    assert 'name="confirm_release_governance"' in final
    assert "Final Release requires fresh authoritative verification." in final
    assert "Decommission blockers" in panel
    assert "External Reference Unverified" in release
    assert "info_tip.render(" not in panel


def test_approver_instructions_match_backend_separation_of_duties() -> None:
    panel = _panel()
    backend = (ROOT / "app/kubernetes/tenant/release_handoff_approval.py").read_text(
        encoding="utf-8"
    )
    assert "Awaiting Independent Approver." in panel
    assert "Acknowledge as Independent Reviewer" in panel
    assert "handoff_plan.requested_by != current_user.id" in panel
    assert "Tenant Manage and Integrations Manage permissions" in panel
    assert "if actor_user_id == plan.get('requested_by'):" in backend
    assert "provider read-back are still separate" in panel


def test_htmx_writes_keep_single_selected_tenant_and_registry_filters() -> None:
    route_common = (ROOT / "app/kubernetes/tenant/route_common.py").read_text(
        encoding="utf-8"
    )
    routes = (ROOT / "app/kubernetes/tenant/routes.py").read_text(encoding="utf-8")
    panel = _panel()
    for field in (
        "manage_tenant_id", "registry_page", "registry_per_page", "registry_search",
        "registry_cluster_id", "registry_environment", "registry_lifecycle_status",
    ):
        assert f'"{field}":' in panel
    assert "hx-vals=" in panel
    assert "request.values.get('manage_tenant_id')" in route_common
    assert "request.values.get(f'registry_{name}')" in route_common
    assert "str(row['tenant'].id) == requested" in route_common
    assert "context['managed_tenant_id']" in route_common
    assert "context.update(_tenant_active_section_context(resolved_section))" in route_common
    assert "context.update(_tenant_active_section_context(active_section))" in routes
    assert "toast_oob=True" in route_common
    assert "get_tenant_registry_context(" in route_common


def test_management_template_parses_with_jinja_and_stays_full_width() -> None:
    source = _template()
    assert "%>" not in source
    Environment(autoescape=True).parse(source)
    panel = _panel()
    sections = (
        'aria-label="Release governance"',
        'aria-label="Namespace attachment"',
        'aria-label="Provider authority"',
        'aria-label="Tenant lifecycle actions"',
    )
    assert all(section in panel for section in sections)
    assert [panel.index(section) for section in sections] == sorted(
        panel.index(section) for section in sections
    )
    assert '<dl class="mt-4 grid min-w-0 gap-4 sm:grid-cols-2">' in panel
    assert "sm:col-span-2" in panel

"""Tenant Registry keeps complex lifecycle actions outside the data table.

This contract is presentation-only: authoritative routes, authorization and
provider evidence remain owned by existing Tenant services.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "app/templates/kubernetes/tenant/partials/_tenant_registry.html"


def _template() -> str:
    return REGISTRY.read_text(encoding="utf-8")


def test_registry_row_exposes_one_labelled_native_dialog_trigger() -> None:
    source = _template()
    row_actions = source.split('<td class="{{ table_ui.cell_classes(action=true) }} align-middle">', 1)[1]
    row_actions = row_actions.split("</td>", 1)[0]

    assert row_actions.count("<button") == 1
    assert "data-kaori-dialog-open" in row_actions
    assert 'data-dialog-target="tenant-registry-actions-{{ tenant.id }}"' in row_actions
    assert "aria-haspopup=\"dialog\"" in row_actions
    assert "aria-controls=" in row_actions
    assert "table_ui.action_classes()" in row_actions
    assert "'Manage' if can_manage else 'View'" in row_actions
    assert "Review Release" not in row_actions
    assert "Decommission" not in row_actions
    assert "<details" not in row_actions


def test_native_modal_is_outside_table_overflow_and_has_accessible_controls() -> None:
    source = _template()
    modal = source.split('data-tenant-registry-actions-dialog', 1)[1]

    assert source.index("data-tenant-registry-actions-dialog") > source.index("registry_ui.footer(")
    assert "data-kaori-native-dialog" in source
    assert "max-w-5xl" in source
    assert "max-h-[calc(100dvh-2rem)]" in source
    assert "overflow-y-auto" in modal
    assert "aria-labelledby=" in source
    assert "aria-describedby=" in source
    assert modal.count("data-kaori-dialog-close") >= 2
    assert "grid grid-cols-3 divide-x" in modal
    assert 'aria-label="Tenant management sections"' in modal
    assert 'space-y-5 px-4 py-5 sm:px-6 sm:py-6' in modal
    assert "lg:grid-cols-3" not in modal
    assert "lg:col-span-2" not in modal
    assert "lg:col-span-1" not in modal
    assert '<aside ' not in modal
    assert "Namespaces" in modal
    assert "Environments" in modal
    assert "Lifecycle" in modal
    assert "Provider Authority" in modal
    assert "Namespace Attachment" in modal
    assert "Release Governance" in modal
    assert "Lifecycle Actions" in modal


def test_existing_managed_routes_and_security_boundaries_are_preserved() -> None:
    source = _template()
    modal = source.split('data-tenant-registry-actions-dialog', 1)[1]

    assert "can_manage and tenant.provider_key == 'capsule'" in modal
    assert "tenant.ownership_status == 'adopted'" in modal
    assert "current_user.has_permission('integrations.manage')" in modal
    assert "if not can_manage" in modal
    assert 'name="csrf_token"' in modal
    assert modal.count('hx-target="#tenant-admin-workspace"') == 9
    assert modal.count('hx-post=') == 9
    assert 'data-capsule-namespace-attach' in modal
    assert 'name="namespace_uid"' in modal
    assert 'name="namespace_resource_version"' in modal
    assert 'review_tenant_release_route' in modal
    assert 'prepare_tenant_release_handoff_route' in modal
    assert 'approve_tenant_release_handoff_route' in modal
    assert 'release_tenant_governance_route' in modal
    assert 'decommission_tenant_route' in modal
    assert 'data-destructive-modal-open' in modal
    assert 'data-destructive-submit-button-id=' in modal
    assert "destructive_modal.render('tenant-decommission-modal'" in source


def test_blocking_evidence_is_visible_in_dialog_not_hover_only() -> None:
    source = _template()
    modal = source.split('data-tenant-registry-actions-dialog', 1)[1]

    assert "Committed Release readiness" in modal
    assert "Release review actions" in modal
    assert "Latest Release Review" in modal
    assert "Release blockers" in modal
    assert "bg-status-warning-soft p-4" in modal
    assert "list-disc space-y-2 pl-5 text-xs leading-5" in modal
    assert "row.release_preflight.blockers" in modal
    assert "No current dependency blockers, but Release execution is not yet admitted." in modal
    assert "Decommission blockers" in modal
    assert "decommission.blockers" in modal
    assert modal.count("table_label.status_label('Blocked', 'warning')") == 1
    assert "table_label.special_label('Blocked'" not in modal
    assert "mt-4 rounded-xl border border-status-warning-border" in modal
    assert "External Reference Unverified" in modal
    assert "data-release-handoff-approval" in modal
    assert "info_tip.render(" not in modal
    # Shared title-level lifecycle glossary is still allowed.
    assert "tenant-registry-status-tip" in source
    assert source.count("data-tenant-registry-actions-dialog") == 1


def test_release_governance_uses_stable_ordered_workflow_not_tablike_disclosures() -> None:
    modal = _template().split('data-tenant-registry-actions-dialog', 1)[1]
    release = modal.split('aria-label="Release governance"', 1)[1].split(
        'aria-label="Namespace attachment"', 1
    )[0]
    workflow_stages = (
        'aria-label="Release readiness"',
        'aria-label="Provider handoff inventory"',
        'aria-label="Governed handoff workflow"',
        'aria-label="Independent verification and release"',
    )
    assert all(stage in release for stage in workflow_stages)
    assert [release.index(stage) for stage in workflow_stages] == sorted(
        release.index(stage) for stage in workflow_stages
    )
    assert 'aria-label="Release governance workflow"' in release

    readiness = release.split(workflow_stages[0], 1)[1].split(workflow_stages[1], 1)[0]
    inventory = release.split(workflow_stages[1], 1)[1].split(workflow_stages[2], 1)[0]
    handoff = release.split(workflow_stages[2], 1)[1].split(workflow_stages[3], 1)[0]
    verification = release.split(workflow_stages[3], 1)[1]

    # Review Release is a write action, not a tab or a disclosure.
    assert 'aria-label="Release review actions"' in readiness
    assert 'review_tenant_release_route' in readiness
    assert 'Latest Release Review' in readiness
    assert 'Release blockers' in readiness
    assert '<details' not in readiness

    # Inventory is always a fixed read-only evidence panel; no toolbar reshuffle.
    assert 'row.release_preflight.handoff_components' in inventory
    assert 'Handoff inventory is read-only provider evidence' in inventory
    assert 'Awaiting Review' in inventory
    assert '<details' not in inventory
    assert 'hx-post=' not in inventory

    # The multi-step handoff is a permanent card, not a flex-wrapped toggle.
    assert 'data-release-handoff-approval' in handoff
    assert 'current_user.has_permission(\'integrations.manage\')' in handoff
    assert 'tenant.prepare_tenant_release_handoff_route' in handoff
    assert 'tenant.approve_tenant_release_handoff_route' in handoff
    assert 'tenant.record_tenant_release_successor_reference_route' in handoff
    assert 'tenant.dry_run_native_release_handoff_route' in handoff
    assert 'tenant.inspect_native_external_handoff_route' in handoff
    assert 'handoff_plan.requested_by != current_user.id' in handoff
    assert 'name="confirm_handoff_approval"' in handoff
    assert 'open:w-full' not in handoff

    assert 'tenant.release_tenant_governance_route' in verification
    assert 'name="confirm_release_governance"' in verification
    assert 'Final Release requires fresh authoritative verification.' in verification
    assert 'row.release_preflight.blockers' in verification
    assert 'data-destructive-modal-open' not in release
    assert 'decommission_tenant_route' not in release


def test_release_workflow_template_parses_with_real_jinja_parser() -> None:
    from jinja2 import Environment

    source = _template()
    assert '%>' not in source
    Environment(autoescape=True).parse(source)


def test_management_sections_use_full_width_cards_in_workflow_order() -> None:
    modal = _template().split('data-tenant-registry-actions-dialog', 1)[1]
    sections = (
        'aria-label="Release governance"',
        'aria-label="Namespace attachment"',
        'aria-label="Provider authority"',
        'aria-label="Tenant lifecycle actions"',
    )

    assert all(section in modal for section in sections)
    indices = [modal.index(section) for section in sections]
    assert indices == sorted(indices)
    assert modal.count('aria-label="Tenant management sections"') == 1
    assert 'lg:grid-cols-3' not in modal
    assert 'lg:order-' not in modal
    assert '<aside ' not in modal

    # The attached Namespace form and provider facts may use their own internal
    # responsive columns without compressing the parent management cards.
    assert 'bg-surface-elevated p-3.5 sm:grid-cols-2' in modal
    assert '<dl class="mt-4 grid min-w-0 gap-4 sm:grid-cols-2">' in modal
    assert 'sm:col-span-2' in modal

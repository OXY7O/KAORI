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
    assert "max-w-4xl" in source
    assert "max-h-[calc(100dvh-2rem)]" in source
    assert "overflow-y-auto" in modal
    assert "aria-labelledby=" in source
    assert "aria-describedby=" in source
    assert modal.count("data-kaori-dialog-close") >= 2
    assert "Committed Lifecycle" in modal
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
    assert "Release blockers" in modal
    assert "row.release_preflight.blockers" in modal
    assert "No current dependency blockers, but Release execution is not yet admitted." in modal
    assert "Decommission blockers" in modal
    assert "decommission.blockers" in modal
    assert "External Reference Unverified" in modal
    assert "data-release-handoff-approval" in modal
    assert "info_tip.render(" not in modal
    # Shared title-level lifecycle glossary is still allowed.
    assert "tenant-registry-status-tip" in source
    assert source.count("data-tenant-registry-actions-dialog") == 1

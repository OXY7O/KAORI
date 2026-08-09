from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_roles_access_registry_uses_kaori_workspace_table_loading_and_modal_standard() -> None:
    index = read('app/templates/access/roles/index.html')
    registry = read('app/templates/access/roles/partials/_registry.html')

    for required in (
        'Role Registry Overview',
        'Role Assignment Flow',
        'components/page_hero.html',
        'components/operational_section_card.html',
        'components/operational_point_flow.html',
        'components/resource_detail_modal.html',
        "access.roles.modal_details",
        'access/roles/partials/_registry.html',
    ):
        assert required in index

    for required in (
        'components/table.html',
        'components/table_label.html',
        'components/loading_bar.html',
        'components/pagination.html',
        'components/resource_detail_modal.html',
        'Search Role',
        'Role Type',
        'Role State',
        'Refreshing Role Registry',
        'role-registry-loading',
        'hx-indicator="#role-registry-loading"',
        'Rows',
        'Previous',
        'Next',
        'View Details',
        "resource_detail_modal.detail_button",
    ):
        assert required in registry

    # The loading bar must live under a full-width header row instead of inside
    # table_ui.block_header_classes(), whose responsive flex layout can compress it.
    assert 'class="border-b border-outline-subtle px-5 py-4 sm:px-6"' in registry
    assert 'table_ui.block_header_classes()' not in registry
    assert 'components/details/_expandable_row.html' not in registry
    assert 'static_detail_row' not in registry
    assert 'Role-Permission Mapping Matrix' not in index
    assert 'role_access_tabs.js' not in index
    assert 'data-role-matrix' not in index


def test_roles_access_detail_modal_exposes_role_specific_coverage_and_boundaries() -> None:
    detail = read('app/templates/access/roles/partials/_role_detail.html')
    routes = read('app/access/roles/routes.py')
    presentation = read('app/access/roles/presentation.py')

    for required in (
        'data-kaori-detail-variant="full-workspace-modal"',
        'Role Identity',
        'Assignment Impact',
        'Provider Defaults',
        'Permission Coverage',
        'Cross-role comparison remains owned by Permission Catalog.',
        'Administrative Boundary',
        'Protected defaults are code-owned',
        'data-destructive-modal-open',
        'role_version',
    ):
        assert required in detail

    assert "@bp.get('/<int:role_id>/details')" in routes
    assert 'def modal_details' in routes
    assert 'build_role_detail_context' in routes
    assert 'def build_role_detail_context' in presentation

    # Keep the technical role key in the primary identity/status cluster.
    assert "{{ table_label.metadata_label(role.name, 'key-round') }}" in detail
    assert 'self-start sm:self-auto' not in detail


def test_role_mutations_are_serialized_and_version_checked() -> None:
    service = read('app/access/roles/service.py')
    routes = read('app/access/roles/routes.py')
    forms = read('app/access/roles/forms.py')

    assert 'with_for_update()' in service
    assert '.populate_existing()' in service
    assert "db.session.expire(role, ['permissions'])" in service
    assert 'def role_version_token' in service
    assert 'def role_version_matches' in service
    assert 'lock_role_for_mutation(role_id)' in routes
    assert "This role changed after the page was opened" in routes
    assert "The role changed after the registry was loaded" in routes
    assert 'role_version = HiddenField' in forms


def test_role_form_uses_sticky_impact_rail_visible_guardrails_and_dependency_evidence() -> None:
    form = read('app/templates/access/roles/form.html')
    for required in (
        'Role Impact',
        'Provider Defaults',
        'Effective Permissions',
        'Permission Modules',
        'xl:sticky xl:top-5',
        "table_label.status_label('Required'",
        'Access Guardrails',
        'Changes apply on the next authorization check.',
        'Design for Responsibility',
        'Dependency Normalization',
        'Super Admin Boundary',
    ):
        assert required in form

    assert '<details class="group overflow-hidden rounded-2xl' not in form
    assert 'active sessions do not cache' not in form


def test_obsolete_role_access_tab_script_is_removed() -> None:
    assert not (ROOT / 'app/static/js/role_access_tabs.js').exists()


def test_role_registry_uses_canonical_pagination_page_size_macro() -> None:
    template = read('app/templates/access/roles/partials/_registry.html')
    assert 'pagination_ui.page_size_classes()' in template
    assert 'pagination_ui.select_classes()' not in template


def test_resource_detail_modal_supports_access_context_without_breaking_inventory_default() -> None:
    component = read('app/templates/components/resource_detail_modal.html')
    assert "context_label='Inventory'" in component
    assert "dialog_max_width='max-w-[100rem]'" in component
    assert "content_driven=false" in component
    assert "{{ _host(resource_type, detail_url_template, footer_text, context_label, dialog_max_width, 'modal', content_driven) }}" in component


def test_role_registry_overview_matches_kaori_registry_overview_visual_grammar() -> None:
    index = read('app/templates/access/roles/index.html')
    for required in (
        'overflow-hidden rounded-2xl border border-outline-default bg-surface-card shadow-sm',
        'text-3xl font-bold tracking-tight text-content-primary',
        'min-h-[11rem]',
        'border-t border-outline-subtle bg-surface-hover px-5 py-4 lg:px-6',
        'Protected Defaults',
        'Custom Role Ownership',
        'Permission Dependencies',
        'Effective Authorization',
    ):
        assert required in index
    assert "operational_section.render(\n            'Role Registry Overview'" not in index

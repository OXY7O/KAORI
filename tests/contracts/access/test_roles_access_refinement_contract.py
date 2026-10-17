from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_roles_access_registry_uses_kaori_workspace_table_loading_and_modal_standard() -> None:
    index = read('app/templates/access/roles/index.html')
    registry = read('app/templates/access/roles/partials/_registry.html')
    shared_registry = read('app/templates/components/table_registry.html')

    for required in (
        'Role Registry Overview',
        'Role Assignment Flow',
        'components/page_hero.html',
        'components/operational_section_card.html',
        'components/operational_point_flow.html',
        'components/resource_detail_modal.html',
        'access.roles.modal_details',
        'access/roles/partials/_registry.html',
    ):
        assert required in index

    for required in (
        'components/table.html',
        'components/table_label.html',
        'components/loading_bar.html',
        'components/table_registry.html',
        'components/resource_detail_modal.html',
        'Search Role',
        'Role Type',
        'Role State',
        'Refreshing Role Registry',
        'role-registry-loading',
        'Rows',
        'View Details',
        'resource_detail_modal.detail_button',
    ):
        assert required in registry

    assert 'registry_ui.footer(' in registry
    for required in (
        'components/pagination.html',
        'hx-indicator="#{{ loading_id }}"',
        '<span>Rows</span>',
        'Previous',
        'Next',
        'pagination_ui.page_size_classes()',
        'data-kaori-canonical-registry-pagination',
    ):
        assert required in shared_registry

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
        'Cross-role comparison remains in Permission Catalog.',
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
    assert 'def ensure_permission_selection_within_delegation_boundary' in service
    assert 'def ensure_role_within_delegation_boundary' in service
    assert 'lock_role_for_mutation(role_id)' in routes
    assert 'This role changed after the page was opened' in routes
    assert 'The role changed after the registry was loaded' in routes
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
        'Delegation Boundary',
        'Outside Ceiling',
        'Super Admin Boundary',
    ):
        assert required in form

    assert '<details class="group overflow-hidden rounded-2xl' not in form
    assert 'active sessions do not cache' not in form


def test_obsolete_role_access_tab_script_is_removed() -> None:
    assert not (ROOT / 'app/static/js/role_access_tabs.js').exists()


def test_role_registry_uses_canonical_pagination_page_size_macro() -> None:
    template = read('app/templates/access/roles/partials/_registry.html')
    shared_registry = read('app/templates/components/table_registry.html')
    assert 'registry_ui.footer(' in template
    assert 'pagination_ui.page_size_classes()' in shared_registry
    assert 'pagination_ui.select_classes()' not in shared_registry
    assert 'pagination_ui.page_size_classes()' not in template


def test_resource_detail_modal_supports_access_context_without_breaking_inventory_default() -> None:
    component = read('app/templates/components/resource_detail_modal.html')
    assert "context_label='Inventory'" in component
    assert "dialog_max_width='max-w-[100rem]'" in component
    assert 'content_driven=false' in component
    assert (
        "{{ _host(resource_type, detail_url_template, footer_text, context_label, dialog_max_width, 'modal', content_driven) }}"
        in component
    )


def test_role_registry_overview_matches_kaori_registry_overview_visual_grammar() -> None:
    index = read('app/templates/access/roles/index.html')
    for required in (
        'overflow-hidden rounded-2xl border border-outline-default bg-surface-card shadow-sm',
        'text-3xl font-bold tracking-tight text-content-primary',
        'min-h-[11rem]',
        'border-t border-outline-subtle bg-surface-hover px-5 py-4 lg:px-6',
        'Protected Defaults',
        'Delegation Boundary',
        'Baseline Drift',
        'Permission Dependencies',
        'Effective Authorization',
    ):
        assert required in index
    assert "operational_section.render(\n            'Role Registry Overview'" not in index


def test_role_form_routes_semantic_borders_through_shared_authority() -> None:
    form = read('app/templates/access/roles/form.html')

    assert 'components/operational_callout.html' in form
    assert "operational_callout.semantic_border_classes('warning')" in form
    assert "operational_callout.semantic_border_classes('critical')" in form
    assert 'border-status-warning-border' not in form
    assert 'border-status-critical-border' not in form



def test_uat_roles_dependency_boundary_uses_short_caption() -> None:
    source = read('app/templates/access/roles/index.html')
    assert 'Code-owned dependencies expand as needed.' in source
    assert "'Permission Dependencies', 'Catalog-Owned'" in source
    assert 'whitespace-nowrap' not in source

def test_review4_role_identity_guide_and_access_guardrail_density() -> None:
    from jinja2 import Environment

    source = read('app/templates/access/roles/form.html')
    Environment().parse(source)
    assert '{% import "components/info_tip.html" as info_tip %}' in source
    assert "info_tip.render('role-identity-fields-guide'," in source
    assert "variant='guide'" in source
    assert "placement='right'" in source
    assert 'Normalized to lowercase underscores and used as the stable backend identifier.</span>' not in source
    assert 'Shown in User Management, role assignment, and identity projection.</span>' not in source
    assert 'form.name(' in source and 'form.display_name(' in source
    assert 'form.errors' in source
    assert 'form.is_active(' in source
    assert 'data-role-state-preview' in source
    assert 'data-role-permission-matrix' in source
    assert 'Active roles serve user and provider assignments; deactivation removes role-derived access.' in source
    guardrails = (
        'Compose reusable roles around operational duties rather than individual user accounts.',
        'Permission dependencies are code-owned and expand automatically when required.',
        'Delegation stays within effective access; Local Database Super Admin is the exception.',
        'Super Admin is a Local Database-only flag, never inherited through role composition.',
    )
    for copy in guardrails:
        assert source.count(copy) == 1
        assert 70 <= len(copy) <= 100
    assert 'whitespace-nowrap' not in source

def test_review4_role_permission_card_description_uses_two_line_minimum() -> None:
    from jinja2 import Environment

    source = read('app/templates/access/roles/form.html')
    Environment().parse(source)
    assert 'mt-1.5 block min-h-10 text-xs leading-5 text-content-muted' in source
    assert "permission_matrix_descriptions.get(permission.key, permission.description or" in source
    assert 'data-role-permission-card' in source
    assert 'data-role-permission' in source
    # Preserve canonical RBAC text; never clip longer permission descriptions.
    assert 'line-clamp-2' not in source


def test_permission_matrix_has_descriptive_copy_for_every_canonical_permission() -> None:
    from jinja2 import Environment
    import yaml

    from app.access.rbac.defaults import DEFAULT_PERMISSIONS, PERMISSION_MATRIX_DESCRIPTIONS

    catalog = yaml.safe_load(read('app/definitions/catalogs/access/rbac/access.yaml'))
    canonical = {item[0]: item[3] for item in DEFAULT_PERMISSIONS}
    records = {item['key']: item for item in catalog['permissions']}
    descriptions = PERMISSION_MATRIX_DESCRIPTIONS

    assert len(canonical) == 64
    assert set(records) == set(canonical) == set(descriptions)
    assert all(records[key]['description'] == description for key, description in canonical.items())
    assert all(records[key]['matrix_description'] == descriptions[key] for key in canonical)
    assert all(80 <= len(value) <= 160 for value in descriptions.values())
    assert len(set(descriptions.values())) == len(descriptions)
    assert descriptions['integrations.manage'] == (
        'Manage integration provider registration, bindings, validation, runtime configuration, and delivery channels.'
    )
    assert 'without exposing' in descriptions['kubernetes_secrets.replace']
    assert 'approve or reject' in descriptions['kubernetes_secrets.approve_reveal'].lower()
    assert 'Local Database' in descriptions['users.reset_password']

    role_form = read('app/templates/access/roles/form.html')
    presentation = read('app/access/roles/presentation.py')
    Environment().parse(role_form)
    assert 'PERMISSION_MATRIX_DESCRIPTIONS' in presentation
    assert "'permission_matrix_descriptions': PERMISSION_MATRIX_DESCRIPTIONS" in presentation
    assert 'permission_matrix_descriptions.get(permission.key,' in role_form
    assert 'data-role-permission-card' in role_form
    assert 'min-h-10' in role_form
    assert 'line-clamp-2' not in role_form
    assert 'permission.description' in role_form  # DB-only registry entries retain their fallback


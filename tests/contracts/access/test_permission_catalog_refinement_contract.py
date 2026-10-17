from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_permission_catalog_get_paths_are_read_only_and_seed_is_command_owned() -> None:
    permission_routes = read('app/access/permissions/routes.py')
    permission_presentation = read('app/access/permissions/presentation.py')
    role_routes = read('app/access/roles/routes.py')
    user_routes = read('app/access/users/routes.py')
    command = read('app/commands/rbac.py')

    for source in (permission_routes, permission_presentation, role_routes, user_routes):
        assert 'seed_default_rbac()' not in source
    assert 'seed_default_rbac()' in command
    assert 'Permission Catalog never mutates or synchronizes the RBAC registry during HTTP GET requests.' in read(
        'app/templates/access/permissions/partials/_permission_detail.html'
    )


def test_permission_catalog_uses_kaori_hero_overview_tabs_tables_loading_and_pagination() -> None:
    index = read('app/templates/access/permissions/index.html')
    workspace = read('app/templates/access/permissions/partials/_workspace.html')
    registry = read('app/templates/access/permissions/partials/_registry.html')
    coverage = read('app/templates/access/permissions/partials/_coverage.html')

    for required in (
        'page_hero.context_card(',
        'Permission Registry Overview',
        'Permission Contracts',
        'Control Modules',
        'Access Administration',
        'Registry Drift',
        'Code Ownership',
        'Dependency Graph',
        'Role Consumption',
        'Authoritative Enforcement',
        'Registry Drift Detected',
        'components/resource_detail_modal.html',
    ):
        assert required in index

    assert 'components/framed_workspace_tabs.html' in workspace
    assert 'Permission Registry' in workspace
    assert 'Role Coverage' in workspace
    assert 'render_navigation' in workspace

    canonical = read('app/templates/components/table_registry.html')
    for view, template in (('registry', registry), ('coverage', coverage)):
        assert 'components/loading_bar.html' in template
        assert 'components/table.html' in template
        assert 'components/table_registry.html' in template
        assert 'registry_ui.filter_form(' in template
        assert 'registry_ui.clear_filters_link(' in template
        assert 'registry_ui.footer(' in template
        assert "'permission-workspace'," in template
        assert f"form_id='permission-{view}-filter-form'" in template
        assert f"'permission-{view}-loading'," in template
        assert "footer_query.pop('per_page', none)" in template
        assert f"control_name='permission-{view}'" in template
        assert 'pagination_ui.numeric_pages(' not in template
        assert 'hx-trigger=' not in template  # shared canonical interaction owner

    assert 'hx-sync="closest section:replace"' in canonical
    assert 'hx-select="#{{ registry_id }}"' in canonical
    assert 'data-kaori-canonical-registry-filter' in canonical
    assert 'data-kaori-canonical-registry-footer' in canonical
    assert 'data-kaori-auto-submit' in canonical
    assert 'name="{{ page_param }}" value="1"' in canonical
    assert 'name="{{ per_page_param }}" value="{{ per_page }}"' in canonical
    assert 'Rows' in canonical and 'Previous' in canonical and 'Next' in canonical
    assert 'hx-indicator="#{{ loading_id }}"' in canonical
    assert 'table_ui.inventory_filter_bar_classes()' in registry
    assert 'table_primitives.filter_layout_classes()' in canonical
    assert 'lg:grid-cols-' not in registry
    assert 'sm:col-span-2 lg:col-span-1' not in registry
    # Filter controls share one vertical rhythm. filter_label_classes() already owns
    # the label-to-control spacing, so local mt-* offsets would misalign search
    # inputs and native selects in some browsers.
    assert 'relative mt-1.5' not in registry
    assert 'class="mt-1.5 {{ table_ui.filter_select_classes() }}"' not in registry
    assert 'table_ui.inventory_filter_bar_classes()' in coverage
    assert 'table_primitives.filter_layout_classes()' in canonical
    assert 'lg:grid-cols-' not in coverage
    assert 'Search Permission' in registry
    assert 'Control Module' in registry
    assert 'Coverage' in registry
    assert 'Delegation Boundary' in registry
    assert 'Registry State' in registry
    assert 'View Details' in registry
    assert 'Role Type' in coverage
    assert 'Role State' in coverage
    assert 'Delegation Boundary' in coverage
    assert 'table-properties' in workspace
    assert 'Toggle all' not in index
    assert 'How RBAC Is Applied' not in index
    assert 'Adding a Permission' not in index
    assert 'xl:sticky xl:top-5' not in index


def test_permission_role_coverage_empty_role_matrix_has_matching_columns() -> None:
    coverage = read('app/templates/access/permissions/partials/_coverage.html')

    # The empty role dimension must still have a matching table header and
    # placeholder body cell; otherwise the default colspan=3 is invalid.
    assert "table_ui.table_classes('min-w-[70rem]' if coverage_roles else 'min-w-[36rem]')" in coverage
    assert '<th scope="col" class="{{ table_ui.header_cell_classes() }} text-center">Role Coverage</th>' in coverage
    assert 'No roles match the current role filters.' in coverage
    assert '{% for role in coverage_roles %}' in coverage
    assert coverage.count('{% else %}') >= 2
    assert '2 + (coverage_roles|length if coverage_roles else 1)' in coverage
    # Header cells intentionally wrap attributes across lines while keeping
    # the Permission column sticky and the Module column aligned.
    assert '<th scope="col"' in coverage
    assert 'class="sticky left-0 z-20 min-w-[18rem] {{ table_ui.header_cell_classes() }} bg-surface-hover"' in coverage
    assert 'class="min-w-[10rem] {{ table_ui.header_cell_classes() }}"' in coverage
    assert 'permission.key in role_permission_keys.get(role.id, [])' in coverage
    # Jinja compilation catches malformed block terminators such as a
    # misspelled `endfor` closer that source-presence checks miss entirely.
    assert '{% endfor %>' not in coverage
    Environment().parse(coverage)


def test_permission_role_coverage_delegation_badge_aligns_with_identity_text() -> None:
    coverage = read('app/templates/access/permissions/partials/_coverage.html')
    registry = read('app/templates/access/permissions/partials/_registry.html')
    table = read('app/templates/components/table.html')
    primitives = read('app/templates/components/table_primitives.html')

    # Role Coverage previously rendered the delegation badge as a sibling of
    # the icon-and-text title cell, so the badge started beneath the icon.
    assert '{% set delegation_badge = table_label.status_label(' in coverage
    assert 'table_ui.title_cell(permission.title,' in coverage
    assert 'delegation_badge) }}' in coverage
    assert coverage.index('set delegation_badge') < coverage.index('table_ui.title_cell(permission.title,')
    assert (
        'table_label.status_label(permission.delegation_tier.label, permission.delegation_tier.tone, permission.delegation_tier.icon)'
        in coverage
    )
    assert '<div class="mt-1.5">{{ table_label.status_label(permission.delegation_tier.label' not in coverage

    # The shared title cell owns the icon geometry. Optional content must be
    # placed inside the existing text column, not via a hard-coded left offset.
    assert "title_cell(name, supporting_text='', icon='', supporting_content=None)" in table
    assert "title_cell(name, supporting_text='', icon='', supporting_content=None)" in primitives
    assert 'table_primitives.title_cell(name, supporting_text, icon, supporting_content)' in table
    assert '{% if supporting_content %}' in primitives
    assert '{{ supporting_content }}' in primitives
    assert primitives.index('{% if supporting_content %}') > primitives.index(
        '{% if supporting_text %}', primitives.index('{% macro title_cell(')
    )
    assert 'ml-[3.125rem]' not in coverage
    # Other tables continue to use the existing three-argument contract.
    assert "table_ui.title_cell(permission.title, permission.key, 'key-round')" in registry


def test_permission_catalog_exposes_drift_dependency_and_cross_role_coverage() -> None:
    service = read('app/access/permissions/service.py')
    detail = read('app/templates/access/permissions/partials/_permission_detail.html')
    coverage = read('app/templates/access/permissions/partials/_coverage.html')

    for required in (
        'missing',
        'metadata_drift',
        'database_only',
        'DEFAULT_PERMISSION_DEPENDENCIES',
        'drift_count',
        'unused_contracts',
        'roles_by_permission_key',
    ):
        assert required in service

    for required in (
        'Permission Identity',
        'Dependency Contract',
        'Requires',
        'Required By',
        'Role Coverage',
        'Registry Boundary',
        'Database Only',
        'flask seed-rbac',
    ):
        assert required in detail or required in service

    assert 'permission.key in role_permission_keys.get(role.id, [])' in coverage
    assert 'Included' in coverage
    assert 'Not Included' in coverage


def test_permission_module_metadata_matches_current_kaori_ownership_without_renaming_keys() -> None:
    defaults = read('app/definitions/catalogs/access/rbac/access.yaml')
    assert 'key: kubernetes_secrets.manage_reveal' in defaults
    assert 'key: jobs.view' in defaults
    assert 'key: platform_operations.view_data_lifecycle' in defaults
    assert 'key: integrations.manage' in defaults

    # Permission keys remain stable authorization contracts.
    for key in (
        'kubernetes_secrets.manage_reveal',
        'jobs.view',
        'platform_operations.view_data_lifecycle',
        'integrations.manage',
    ):
        assert key in defaults


def test_permission_detail_modal_supports_string_permission_keys() -> None:
    js = read('app/static/js/detail_rows.js')
    routes = read('app/access/permissions/routes.py')
    index = read('app/templates/access/permissions/index.html')
    assert "template.includes('__detail__')" in js
    assert "template.replace('__detail__', encodeURIComponent(detailId))" in js
    assert "@bp.get('/<string:permission_key>/details')" in routes
    assert "permission_key='__detail__'" in index
    assert "dialog_max_width='max-w-5xl'" in index
    assert 'content_driven=true' in index
    modal = read('app/templates/components/resource_detail_modal.html')
    assert 'content_driven=false' in modal
    assert 'h-auto max-h-[calc(100dvh-1rem)]' in modal


def test_permission_delegation_authority_shares_evidence_column_alignment() -> None:
    detail = read('app/templates/access/permissions/partials/_permission_detail.html')

    # Shared inventory_section controls section padding. A nested Violet
    # border/padding shifts Authority to the right of adjacent evidence rows.
    assert '<div class="min-w-0 max-w-3xl" data-kaori-permission-policy>' in detail
    authority = detail.split('data-kaori-permission-policy>', 1)[1].split('{% endcall %}', 1)[0]
    assert 'border-l-2' not in authority
    assert 'pl-3.5' not in authority
    assert '<p class="text-xs font-semibold text-content-secondary">Authority</p>' in authority
    assert 'Only the Local Database Super Admin break-glass authority' in authority
    assert 'Non-Super Admin delegation requires this permission' in authority
    assert '<div class="min-w-0 max-w-3xl" data-kaori-permission-registry-facts>' in detail
    Environment().parse(detail)


def test_permission_catalog_detail_uses_count_free_shared_modal_hierarchy() -> None:
    workspace = read('app/templates/access/permissions/partials/_workspace.html')
    detail = read('app/templates/access/permissions/partials/_permission_detail.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert (
        "('registry', 'Permission Registry', 'list-tree', url_for('access.permissions.index', view='registry'))"
        in workspace
    )
    assert (
        "('coverage', 'Role Coverage', 'table-properties', url_for('access.permissions.index', view='coverage'))"
        in workspace
    )
    assert 'summary.canonical_permissions' not in workspace
    assert 'roles|length' not in workspace
    assert 'framed_tabs.render_navigation(' in workspace

    # Preserve the canonical content-driven modal with an extracted,
    # nonnumeric summary. The body uses the approved single resource-sheet
    # surface and five horizontal evidence bands, rather than stacked cards.
    assert 'data-resource-detail-header' in detail
    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'detail_ui.summary_strip([' in detail
    assert '], compact=true, borderless=true)' in detail
    assert 'data-resource-detail-summary' in shared
    assert (
        "{% macro summary_strip(metrics, columns=4, compact=false, borderless=false, layout='default', pinned=true)"
        in shared
    )
    assert 'data-kaori-summary-variant="borderless"' in shared
    # The permission summary uses the borderless branch of the approved shared
    # macro. Legacy callers keep the original divided variant by default.
    assert "'min-w-0 py-0.5' if borderless" in shared
    assert "'min-w-0 border-b border-outline-subtle" in shared
    assert 'sm:border-r' in shared
    assert 'gap-x-6 gap-y-3' in shared
    assert "('Role Mapping', 'Mapped' if permission.role_count else 'Unassigned', '')" in detail
    assert "('Active Usage', 'In Use' if permission.active_user_count else 'No Effective Users', '')" in detail
    assert "('JIT Projection', 'Configured' if permission.jit_provider_count else 'Not Configured', '')" in detail
    assert "('Requires', 'Present' if effective_requires else 'None', '')" in detail
    # The compact metrics strip omits the Control Module, but the full
    # Permission Identity sheet must retain that authoritative detail.
    summary = detail.split('detail_ui.summary_strip([', 1)[1].split('], compact=true, borderless=true)', 1)[0]
    assert "('Control Module', permission.module_label" not in summary
    assert "detail_ui.stacked_detail_row('Control Module', permission.module_label)" in detail

    assert 'data-kaori-permission-detail-layout="unified-resource-sheet"' in detail
    assert 'detail_ui.resource_sheet()' in detail
    assert 'data-kaori-unified-resource-sheet' in shared
    assert 'data-kaori-inventory-section-layout="resource-sheet-band"' in shared
    assert 'compact_layout=false) -%}' in shared
    assert "'min-w-0 px-4 py-3.5 sm:px-5 xl:px-6 xl:py-4' if compact_layout" in shared
    assert "'mt-1 break-words text-xs leading-4 text-content-muted" in shared
    assert detail.count('compact_layout=true') == 5
    assert 'data-kaori-permission-identity-facts' in detail
    assert 'data-kaori-permission-dependency-facts' in detail
    assert 'data-kaori-permission-policy' in detail
    assert 'data-kaori-permission-registry-facts' in detail
    assert '<div class="min-w-0 max-w-3xl" data-kaori-permission-policy>' in detail
    assert 'border-l-2 border-brand-outline pl-3.5' not in detail
    assert "table_ui.table_classes('min-w-[32rem]')" in detail
    assert "table_ui.table_classes('min-w-[38rem]')" not in detail
    assert detail.count('detail_ui.inventory_section(') == 5
    assert 'detail_ui.detail_card(' not in detail
    assert 'data-kaori-permission-detail-layout="full-width-stack"' not in detail
    assert 'lg:grid-cols-2' not in detail
    expected_sections = (
        "inventory_section('Permission Identity'",
        "inventory_section('Dependency Contract'",
        "inventory_section('Delegation Boundary'",
        "inventory_section('Registry Boundary'",
        "inventory_section('Role Coverage'",
    )
    assert [detail.index(marker) for marker in expected_sections] == sorted(
        detail.index(marker) for marker in expected_sections
    )
    assert 'sm:grid-cols-2' in detail  # compact identity/dependency facts only
    assert "detail_ui.stacked_detail_row('Permission Key', permission.key)" in detail
    assert 'permission.description or' in detail
    assert "table_label.metadata_label(item.title, 'arrow-down-left', true)" in detail
    assert "table_label.metadata_label(item.title, 'arrow-up-right', true)" in detail
    assert "detail_ui.stacked_detail_row('Stored Module', permission.database_module" in detail
    assert "detail_ui.stacked_detail_row('Stored Action', permission.database_action" in detail
    assert 'max-w-3xl' in detail
    assert 'border-t border-outline-subtle pt-3' in detail
    assert 'aria-label="Permission role coverage"' in detail

    # Keep source-derived semantics, but never render count badges or numeric KPIs in the detail.
    assert 'permission.role_count ~' not in detail
    assert '{{ permission.role_count }}' not in detail
    assert '{{ permission.active_user_count }}' not in detail
    assert '{{ permission.jit_provider_count }}' not in detail
    assert '{{ role.active_user_count }}' not in detail
    assert '{{ role.jit_provider_count }}' not in detail
    assert "badge='Mapped' if role_rows else 'Unassigned'" in detail
    assert "'In Use' if role.active_user_count else 'No Effective Users'" in detail
    assert "'Configured' if role.jit_provider_count else 'Not Configured'" in detail
    assert 'permission.key' in detail
    assert 'permission.delegation_tier' in detail
    assert 'permission.state_key' in detail
    assert 'requires' in detail and 'required_by' in detail
    assert 'Permission Catalog never mutates or synchronizes the RBAC registry during HTTP GET requests.' in detail


def test_permission_effective_usage_excludes_inactive_role_assignments() -> None:
    """Active membership through an inactive role must not claim active access."""
    from types import SimpleNamespace

    from app.access.permissions.service import _role_impact

    active_user = SimpleNamespace(id=101, is_active=True)
    inactive_role_only_user = SimpleNamespace(id=202, is_active=True)
    inactive_user = SimpleNamespace(id=303, is_active=False)
    active_role = SimpleNamespace(id=11, is_active=True, users=[active_user, active_user, inactive_user])
    disabled_role = SimpleNamespace(id=12, is_active=False, users=[inactive_role_only_user, active_user])
    enabled_jit_provider = SimpleNamespace(id=55)

    assert _role_impact([disabled_role], enabled_jit_providers_by_role={12: [enabled_jit_provider]}) == {
        'active_user_count': 0,
        'jit_provider_count': 1,
    }
    assert _role_impact([active_role, disabled_role], enabled_jit_providers_by_role={}) == {
        'active_user_count': 1,
        'jit_provider_count': 0,
    }
    assert _role_impact([active_role], enabled_jit_providers_by_role={})['active_user_count'] == 1
    assert _role_impact([], enabled_jit_providers_by_role={})['active_user_count'] == 0



def test_uat_role_coverage_result_count_matches_permission_registry_title_placement() -> None:
    registry = read('app/templates/access/permissions/partials/_registry.html')
    coverage = read('app/templates/access/permissions/partials/_coverage.html')
    for source, title in ((registry, 'Permission Registry'), (coverage, 'Role Coverage')):
        header = source.split('</header>', 1)[0]
        assert header.index(f'>{title}</h2>') < header.index('table_label.result_count(matching_count)')
        assert header.index('table_label.result_count(matching_count)') < header.index('table_ui.block_description_classes()')
        assert header.count('table_label.result_count(matching_count)') == 1
    assert "matching_count ~ ' Matching '" not in coverage
    workspace = read('app/templates/access/permissions/partials/_workspace.html')
    assert 'result_count(' not in workspace



def test_uat_laptop_permission_overview_descriptions_fit_compact_cards() -> None:
    source = read('app/templates/access/permissions/index.html')
    metric_copy = (
        'Code-owned authorization contracts.',
        'Source-owned control modules.',
        'Local Database Super Admin-only delegation.',
        'Code/database drift needs review.',
    )
    boundary_copy = (
        'Code owns permissions and delegation.',
        'Code-owned dependencies auto-expand.',
        'Server-side guards enforce access.',
    )
    for phrase in (*metric_copy, *boundary_copy):
        assert phrase in source
        assert len(phrase) <= 48
    assert 'summary.unused_contracts' in source
    assert 'summary.access_administration_contracts' in source
    assert 'summary.drift_count' in source
    assert 'whitespace-nowrap' not in source

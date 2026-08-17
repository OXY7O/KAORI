from pathlib import Path

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

    for template in (registry, coverage):
        assert 'components/loading_bar.html' in template
        assert 'components/table.html' in template
        assert 'components/pagination.html' in template
        assert 'Rows' in template
        assert 'Previous' in template
        assert 'Next' in template
        assert 'hx-indicator=' in template

    assert 'table_ui.inventory_filter_bar_classes()' in registry
    assert 'grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-4' in registry
    assert 'sm:col-span-2 lg:col-span-1' in registry
    # Filter controls share one vertical rhythm. filter_label_classes() already owns
    # the label-to-control spacing, so local mt-* offsets would misalign search
    # inputs and native selects in some browsers.
    assert 'relative mt-1.5' not in registry
    assert 'class="mt-1.5 {{ table_ui.filter_select_classes() }}"' not in registry
    assert 'table_ui.inventory_filter_bar_classes()' in coverage
    assert 'grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-5' in coverage
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

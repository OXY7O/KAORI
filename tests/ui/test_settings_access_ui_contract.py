from pathlib import Path

SETTINGS_ACCESS_HERO_TEMPLATES = (
    Path('app/templates/settings/general/partials/_hero.html'),
    Path('app/templates/settings/account/partials/_hero.html'),
    Path('app/templates/settings/secret_reveal/index.html'),
    Path('app/templates/settings/reports/partials/_placeholder.html'),
    Path('app/templates/users/partials/_hero.html'),
    Path('app/templates/users/form.html'),
    Path('app/templates/users/reset_password.html'),
    Path('app/templates/users/providers/index.html'),
    Path('app/templates/users/providers/form.html'),
    Path('app/templates/users/external_identities.html'),
    Path('app/templates/settings/roles/index.html'),
    Path('app/templates/settings/roles/form.html'),
    Path('app/templates/settings/permissions/index.html'),
    Path('app/templates/notifications/activity.html'),
)


def test_settings_and_access_heroes_use_shared_kaori_contract() -> None:
    required_fragments = (
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'page_hero.content_classes()',
        'page_hero.aside_classes()',
        'text-2xl font-bold leading-tight tracking-tight text-brand-foreground lg:text-[1.75rem]',
    )

    for template_path in SETTINGS_ACCESS_HERO_TEMPLATES:
        source = template_path.read_text(encoding='utf-8')
        missing = [fragment for fragment in required_fragments if fragment not in source]
        assert not missing, f'{template_path} is missing hero contract fragments: {missing}'


def test_shared_settings_access_hero_has_fixed_desktop_geometry() -> None:
    source = Path('app/templates/components/page_hero.html').read_text(encoding='utf-8')

    required_fragments = (
        'min-h-[15.5rem]',
        'xl:h-[15.5rem]',
        'xl:h-full xl:min-h-0 xl:grid-cols-12',
        'xl:[&>*]:h-full',
        'xl:[&>*]:min-h-0',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Shared Settings/Access hero geometry is incomplete: {missing}'

    user_hero = Path('app/templates/users/partials/_hero.html').read_text(encoding='utf-8')
    add_user = Path('app/templates/users/form.html').read_text(encoding='utf-8')
    assert "page_hero.intro('users-round', 'Access Administration', 'users-round')" in user_hero
    assert 'page_hero.shell_classes()' in add_user


def test_general_and_account_tabs_use_htmx_without_full_page_reload() -> None:
    contracts = (
        (
            Path('app/templates/settings/general/partials/_tabs.html'),
            '#general-settings-page',
            ('time-locale', 'regional-format', 'system-information'),
        ),
        (
            Path('app/templates/settings/account/partials/_tabs.html'),
            '#account-authentication-page',
            ('profile', 'activity', 'credentials'),
        ),
    )

    for template_path, target, tab_names in contracts:
        source = template_path.read_text(encoding='utf-8')
        assert source.count(f'hx-target="{target}"') == len(tab_names)
        assert source.count('hx-swap="outerHTML"') == len(tab_names)
        assert source.count('hx-push-url="true"') == len(tab_names)
        for tab_name in tab_names:
            assert f"tab='{tab_name}'" in source
            assert 'hx-get=' in source


def test_sidebar_collapse_navigation_is_removed() -> None:
    layout_source = Path('app/templates/layouts/app.html').read_text(encoding='utf-8')
    sidebar_source = Path('app/templates/components/navigation/sidebar.html').read_text(encoding='utf-8')

    assert 'Collapse navigation' not in sidebar_source
    assert 'toggle-sidebar' not in sidebar_source
    assert '@toggle-sidebar.window' not in layout_source
    assert 'x-data="{ sidebarOpen:' not in layout_source
    assert 'sidebar-collapsed' not in layout_source
    assert 'kubereport.sidebarOpen' not in layout_source


def test_permission_catalog_uses_section_based_standard_pagination() -> None:
    source = Path('app/templates/settings/permissions/index.html').read_text(encoding='utf-8')

    required_fragments = (
        'page: 1',
        'perPage: 5',
        'filteredModules()',
        'pageModules()',
        'this.filteredModules().length / this.perPage',
        'this.pageModules().includes(moduleName)',
        'this.pageModules().includes(permission.module)',
        'x-model.number="perPage"',
        '<option value="5">5</option>',
        '<option value="10">10</option>',
        '<option value="25">25</option>',
        '<option value="50">50</option>',
        'Showing <strong',
        'filteredModules().length"></strong> sections',
        'aria-label="Sections per page"',
        'Previous',
        'Next',
        'No matching permissions',
        'grid items-start gap-6',
    )

    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Permission Catalog section pagination is incomplete: {missing}'
    assert 'Showing sections <strong' not in source
    assert '<span class="text-xs">Sections</span>' not in source
    assert 'this.filtered().length / this.perPage' not in source
    assert 'pageItems()' not in source


def test_rbac_ownership_and_authorization_flow_are_explicit() -> None:
    roles_source = Path('app/templates/settings/roles/index.html').read_text(encoding='utf-8')
    permissions_source = Path('app/templates/settings/permissions/index.html').read_text(encoding='utf-8')

    required_role_flow_fragments = (
        'Role assignment flow',
        'Permission Catalog',
        'Role Composition',
        'User Management',
        'One active role is assigned to each account',
        'Super Admin remains a separate emergency authority flag',
    )
    missing_role = [fragment for fragment in required_role_flow_fragments if fragment not in roles_source]
    assert not missing_role, f'Roles & Access flow is incomplete: {missing_role}'
    assert '>Role model<' not in roles_source

    required_permission_flow_fragments = (
        '<details open class="group overflow-hidden',
        'How RBAC is applied',
        'group-open:rotate-180',
        'Permission Catalog',
        'flask seed-rbac',
        'Roles &amp; Access',
        'User assignment',
        'User Management assigns one active role to each account.',
        'Server enforcement',
        'Security boundary:',
        'server-side permission checks are authoritative',
    )
    missing_permission = [
        fragment for fragment in required_permission_flow_fragments if fragment not in permissions_source
    ]
    assert not missing_permission, f'Permission Catalog RBAC flow is incomplete: {missing_permission}'

    boundary_position = permissions_source.index('Security boundary:')
    block_start = permissions_source.rfind('<div class="', 0, boundary_position)
    block_fragment = permissions_source[block_start:boundary_position]
    assert 'border-brand-outline' in block_fragment
    assert 'bg-kaori-soft' in block_fragment
    assert 'text-kaori-primary' in block_fragment


def test_roles_and_permissions_use_identity_access_overview_pattern() -> None:
    roles_source = Path('app/templates/settings/roles/index.html').read_text(encoding='utf-8')
    permissions_source = Path('app/templates/settings/permissions/index.html').read_text(encoding='utf-8')

    for source, heading in (
        (roles_source, 'Role &amp; Access Overview'),
        (permissions_source, 'Permission Registry Overview'),
    ):
        assert heading in source
        assert 'overflow-hidden rounded-2xl border border-outline-default bg-surface-card shadow-sm' in source
        assert 'grid gap-px bg-outline-subtle md:grid-cols-2 xl:grid-cols-4' in source
        assert 'border-t border-outline-subtle bg-surface-hover' in source
        assert 'min-h-[12rem]' in source


def test_roles_page_has_dynamic_registry_and_mapping_matrix_tabs() -> None:
    source = Path('app/templates/settings/roles/index.html').read_text(encoding='utf-8')
    script = Path('app/static/js/role_access_tabs.js').read_text(encoding='utf-8')

    required_template_fragments = (
        'data-role-access-tabs',
        'data-role-access-tab="registry"',
        'data-role-access-tab="matrix"',
        'data-role-access-panel="registry"',
        'data-role-access-panel="matrix"',
        'Role-Permission Mapping Matrix',
        '{% for role in roles %}',
        '{% for module_name, module_permissions in permissions_by_module.items() %}',
        'permission.key in role_permission_keys.get(role.id, [])',
        'New custom roles appear automatically after creation.',
        'Super Admin is intentionally excluded.',
        "js/role_access_tabs.js",
    )
    missing = [fragment for fragment in required_template_fragments if fragment not in source]
    assert not missing, f'Role mapping matrix contract is incomplete: {missing}'

    assert "window.location.hash === '#role-permission-matrix'" in script
    assert "panel.hidden = panel.dataset.roleAccessPanel !== targetName" in script
    assert "button.setAttribute('aria-selected'" in script


def test_role_form_guardrails_and_global_permission_toggle_are_available() -> None:
    source = Path('app/templates/settings/roles/form.html').read_text(encoding='utf-8')
    script = Path('app/static/js/role_permission_editor.js').read_text(encoding='utf-8')

    required_form_fragments = (
        '<details open class="group overflow-hidden',
        'Access guardrails',
        'Design for responsibility',
        'Dependency normalization',
        'Assignment impact',
        'Super Admin boundary',
        'data-role-toggle-all',
        'data-role-toggle-all-label',
        'Select all',
    )
    missing = [fragment for fragment in required_form_fragments if fragment not in source]
    assert not missing, f'Role editor guardrail/toggle contract is incomplete: {missing}'

    required_script_fragments = (
        "root.querySelector('[data-role-toggle-all]')",
        "root.querySelector('[data-role-toggle-all-label]')",
        "toggleAllButton?.addEventListener('click'",
        "toggleAllLabel.textContent = allSelected ? 'Clear all' : 'Select all'",
        "toggleAllButton.setAttribute('aria-pressed'",
    )
    missing_script = [fragment for fragment in required_script_fragments if fragment not in script]
    assert not missing_script, f'Global permission toggle implementation is incomplete: {missing_script}'

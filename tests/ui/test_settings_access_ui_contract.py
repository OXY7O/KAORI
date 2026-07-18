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
        'min-h-[12rem]',
        'text-2xl font-bold leading-tight tracking-tight text-brand-foreground lg:text-[1.75rem]',
    )

    for template_path in SETTINGS_ACCESS_HERO_TEMPLATES:
        source = template_path.read_text(encoding='utf-8')
        missing = [fragment for fragment in required_fragments if fragment not in source]
        assert not missing, f'{template_path} is missing hero contract fragments: {missing}'


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
        'Showing sections <strong',
        '<span class="text-xs">Sections</span>',
        'Previous',
        'Next',
        'No matching permissions',
    )

    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Permission Catalog section pagination is incomplete: {missing}'
    assert 'this.filtered().length / this.perPage' not in source
    assert 'pageItems()' not in source


def test_rbac_ownership_and_authorization_flow_are_explicit() -> None:
    roles_source = Path('app/templates/settings/roles/index.html').read_text(encoding='utf-8')
    permissions_source = Path('app/templates/settings/permissions/index.html').read_text(encoding='utf-8')

    role_model_copy = (
        'Roles & Access builds reusable role profiles from the Permission Catalog. '
        'User Management assigns one active role to each user. '
        'Super Admin remains a separate emergency authority flag, not a normal role.'
    )
    assert role_model_copy in roles_source

    required_flow_fragments = (
        'How RBAC is applied',
        'Permission Catalog',
        'flask seed-rbac',
        'Roles &amp; Access',
        'User assignment',
        'User Management assigns one active role to each account.',
        'Server enforcement',
        'Security boundary:',
        'server-side permission checks are authoritative',
    )
    missing = [fragment for fragment in required_flow_fragments if fragment not in permissions_source]
    assert not missing, f'Permission Catalog RBAC flow is incomplete: {missing}'

    boundary_position = permissions_source.index('Security boundary:')
    block_start = permissions_source.rfind('<div class="', 0, boundary_position)
    block_fragment = permissions_source[block_start:boundary_position]
    assert 'border-brand-outline' in block_fragment
    assert 'bg-kaori-soft' in block_fragment
    assert 'text-kaori-primary' in block_fragment

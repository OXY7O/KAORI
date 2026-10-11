from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_access_overview_uses_domain_owned_summary_only_paths() -> None:
    overview = read('app/access/overview/presentation.py')
    assert 'build_roles_overview_summary()' in overview
    assert 'build_permission_registry_summary()' in overview
    assert 'build_roles_index_context(' not in overview
    assert 'build_permission_registry_snapshot(' not in overview
    for forbidden in ('db.session', 'User.query', 'Role.query', 'Permission.query'):
        assert forbidden not in overview


def test_role_summary_is_shared_by_full_registry_and_overview() -> None:
    roles = read('app/access/roles/presentation.py')
    assert 'def _build_roles_summary(' in roles
    assert 'def build_roles_overview_summary(' in roles
    assert 'return _build_roles_summary(' in roles
    assert 'summary = _build_roles_summary(' in roles
    assert 'lazyload(Role.users)' in roles
    assert 'lazyload(Role.role_permissions)' in roles
    summary_block = roles.split('def build_roles_overview_summary(', 1)[1].split(
        'def build_roles_index_context(', 1
    )[0]
    for unnecessary_detail in ('role_rows', 'role_version_token', 'build_pagination_window'):
        assert unnecessary_detail not in summary_block


def test_permission_summary_reuses_registry_contract_without_detail_expansion() -> None:
    permission = read('app/access/permissions/service.py')
    fast = permission.split('def build_permission_registry_summary(', 1)[1]
    assert 'return _registry_summary(' in fast
    assert '_registry_state(canonical, registered)' in fast
    assert 'RolePermission.permission_id' in fast
    assert 'lazyload(Permission.role_permissions)' in fast
    for unwanted in ('_build_contract_row(', '_dependency_closure(', '_role_impact(', 'Role.query'):
        assert unwanted not in fast
    assert 'role_mappings=sum(len(role.permissions) for role in roles)' in permission
    assert 'role_mappings=sum(mapping_counts.values())' in permission

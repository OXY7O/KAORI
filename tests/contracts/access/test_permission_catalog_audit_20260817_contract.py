from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_permission_catalog_source_controls_module_and_delegation_taxonomy() -> None:
    catalog = read('app/definitions/catalogs/rbac/access.yaml')
    defaults = read('app/rbac/defaults.py')
    service = read('app/access/permissions/service.py')

    assert 'control_modules:' in catalog
    assert 'access_administration_permissions:' in catalog
    assert 'PERMISSION_MODULE_LABELS' in defaults
    assert 'permissions reference unknown control modules' in defaults
    assert 'control_modules contains unused module definitions' in defaults
    assert 'ACCESS_ADMINISTRATION_PERMISSIONS' in service
    assert 'DELEGATION_TIER_PRESENTATION' in service
    assert "'access_admin'" in service
    assert "'standard'" in service


def test_permission_catalog_exposes_delegation_impact_and_transitive_dependencies() -> None:
    service = read('app/access/permissions/service.py')
    presentation = read('app/access/permissions/presentation.py')
    registry = read('app/templates/access/permissions/partials/_registry.html')
    coverage = read('app/templates/access/permissions/partials/_coverage.html')
    detail = read('app/templates/access/permissions/partials/_permission_detail.html')

    for required in (
        '_dependency_closure',
        'effective_requires',
        'active_user_count',
        'jit_provider_count',
        'database_only_in_use_count',
        'access_administration_contracts',
    ):
        assert required in service

    assert 'PERMISSION_DELEGATION_OPTIONS' in presentation
    assert "filters['delegation']" in presentation
    for template in (registry, coverage):
        assert 'Delegation Boundary' in template
        assert 'Access Administration' in template
        assert 'Standard Capability' in template
    assert 'Effective Requirements' in detail
    assert 'Active Users' in detail
    assert 'JIT Paths' in detail
    assert 'Local Database Super Admin' in detail


def test_permission_contract_keys_follow_current_domain_ownership_without_runtime_aliases() -> None:
    catalog = read('app/definitions/catalogs/rbac/access.yaml')
    migration = read('migrations/versions/20260817_permission_contract_ownership.py')
    sidebar = read('app/templates/components/navigation/sidebar.html')
    activity_routes = read('app/access/activity_audit/routes.py')

    assert 'key: integrations.manage' in catalog
    assert 'key: activity_audit.view' in catalog
    assert 'settings.manage_integrations' not in catalog
    assert 'settings.view_operational_activity' not in catalog
    assert "current_user.has_permission('integrations.manage')" in sidebar
    assert "@permission_required('activity_audit.view')" in activity_routes
    assert "'source_key': 'settings.manage_integrations'" in migration
    assert "'target_key': 'integrations.manage'" in migration
    assert "'source_key': 'settings.view_operational_activity'" in migration
    assert "'target_key': 'activity_audit.view'" in migration


def test_permission_catalog_remains_read_only_and_convergence_command_owned() -> None:
    routes = read('app/access/permissions/routes.py')
    service = read('app/access/permissions/service.py')
    detail = read('app/templates/access/permissions/partials/_permission_detail.html')

    assert '@bp.post' not in routes
    assert 'seed_default_rbac' not in routes
    assert 'db.session.commit' not in routes
    assert 'db.session.commit' not in service
    assert 'flask seed-rbac' in detail


def test_permission_catalog_registry_summary_is_wired_once_without_recursive_shadow_state() -> None:
    service = read('app/access/permissions/service.py')
    summary_block = service.split('def _registry_summary(', 1)[1].split('def build_permission_registry_snapshot(', 1)[0]
    snapshot_block = service.split('def build_permission_registry_snapshot(', 1)[1]

    assert "canonical_contracts = [row for row in contracts if row['code_owned']]" in summary_block
    assert "drift_contracts = [row for row in contracts if row['state_key'] != 'canonical']" in summary_block
    assert 'database_only_in_use_count = sum(' in summary_block
    assert '_registry_summary(' not in summary_block
    assert 'summary = _registry_summary(' in snapshot_block
    assert "'summary': summary" in snapshot_block

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_jobs_routes_use_dedicated_view_and_cancel_permissions() -> None:
    routes = read('app/integrations/routes.py')
    assert "@permission_required('jobs.view')\ndef jobs" in routes
    assert "@permission_required('jobs.cancel')\ndef cancel_job" in routes


def test_jobs_permissions_are_registered_and_dependency_is_enforced() -> None:
    defaults = read('app/rbac/defaults.py')
    service = read('app/rbac/service.py')
    assert "('jobs.view', 'operations', 'view_jobs'" in defaults
    assert "('jobs.cancel', 'operations', 'cancel_jobs'" in defaults
    assert "'jobs.cancel': {'jobs.view'}" in service


def test_platform_operations_navigation_uses_jobs_view_permission() -> None:
    sidebar = read('app/templates/components/navigation/sidebar.html')
    active = read('app/templates/integrations/jobs/partials/_active_jobs.html')
    registry = read('app/templates/integrations/jobs/partials/_registry.html')
    overview = read('app/templates/integrations/overview.html')
    assert "current_user.has_permission('jobs.view')" in sidebar
    assert "current_user.has_permission('jobs.cancel')" in active
    assert "current_user.has_permission('jobs.cancel')" in registry
    assert "current_user.has_permission('jobs.view')" in overview


def test_rbac_migration_preserves_existing_custom_role_access() -> None:
    migration = read('migrations/versions/20260721_job_operations_rbac.py')
    assert "down_revision = '20260721_data_lifecycle'" in migration
    assert "'settings.manage_integrations': ('jobs.view', 'jobs.cancel')" in migration
    assert "'settings.view_data_lifecycle': ('jobs.view',)" in migration
    assert "'settings.view_operational_activity': ('jobs.view',)" in migration

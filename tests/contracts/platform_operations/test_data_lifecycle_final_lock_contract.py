from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_data_lifecycle_is_owned_by_platform_operations_end_to_end() -> None:
    assert (ROOT / 'app/platform_operations/data_lifecycle/routes.py').exists()
    assert (ROOT / 'app/platform_operations/data_lifecycle/service.py').exists()
    assert (ROOT / 'app/platform_operations/data_lifecycle/presentation.py').exists()
    assert (ROOT / 'app/templates/platform_operations/data_lifecycle/index.html').exists()
    assert not (ROOT / 'app/templates/settings/data_lifecycle').exists()
    assert not (ROOT / 'app/settings/data_lifecycle').exists()
    assert (ROOT / 'app/settings/data_lifecycle_compat.py').exists()

    platform_init = read('app/platform_operations/__init__.py')
    assert "bp.register_blueprint(data_lifecycle_bp, url_prefix='/data-lifecycle')" in platform_init

    routes = read('app/platform_operations/data_lifecycle/routes.py')
    assert "@permission_required('platform_operations.view_data_lifecycle')" in routes
    assert "@permission_required('platform_operations.manage_data_lifecycle')" in routes
    assert "@permission_required('platform_operations.export_data_lifecycle')" in routes
    assert 'settings.data_lifecycle' not in routes


def test_settings_data_lifecycle_is_redirect_only_compatibility() -> None:
    compatibility = read('app/settings/data_lifecycle_compat.py')
    assert 'code=302' in compatibility
    assert 'code=308' in compatibility
    assert 'platform_operations.data_lifecycle.index' in compatibility
    assert 'platform_operations.data_lifecycle.save_policy' in compatibility
    assert 'render_template' not in compatibility
    assert 'app.retention' not in compatibility
    assert 'enqueue_canonical_job' not in compatibility


def test_data_lifecycle_uses_shared_workspace_and_archive_history_contract() -> None:
    index = read('app/templates/platform_operations/data_lifecycle/index.html')
    history = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')

    assert 'components/framed_workspace_tabs.html' in index
    assert 'framed_workspace_tabs.render(' in index
    assert 'role="tablist"' not in index
    assert 'Planned Domains' not in index
    assert 'bg-white' not in index
    assert 'Execution Boundary' in index
    assert "url_for('jobs.executions')" in index

    assert 'Archive History' in history
    assert 'Lifecycle Execution History' not in history
    assert "{{ 'Archive' if pager.total == 1 else 'Archives' }}" in history
    assert '>Rows</span>' in history
    assert 'aria-label="Rows Per Page"' in history


def test_data_lifecycle_navigation_and_breadcrumb_are_platform_owned() -> None:
    menu = read('app/templates/components/navigation/platform_operations_menu.html')
    settings_menu = read('app/templates/components/navigation/settings_menu.html')
    sidebar = read('app/templates/components/navigation/sidebar.html')
    breadcrumb = read('app/common/navigation.py')

    assert 'Jobs &amp; Executions' in menu
    assert 'Data Lifecycle' in menu
    assert 'Kubernetes Administration' in menu
    assert menu.index('Jobs &amp; Executions') < menu.index('Data Lifecycle') < menu.index('Kubernetes Administration')
    assert "url_for('platform_operations.data_lifecycle.index')" in menu
    assert "has_permission('platform_operations.view_data_lifecycle')" in sidebar
    assert 'Data Lifecycle' not in settings_menu
    assert "endpoint.startswith('platform_operations.data_lifecycle.')" in breadcrumb


def test_data_lifecycle_rbac_cutover_preserves_permission_rows_in_place() -> None:
    defaults = read('app/rbac/defaults.py')
    migration = read('migrations/versions/20260808_data_lifecycle_platform_operations.py')

    for key in (
        'platform_operations.view_data_lifecycle',
        'platform_operations.manage_data_lifecycle',
        'platform_operations.export_data_lifecycle',
    ):
        assert key in defaults

    for old, new in (
        ('settings.view_data_lifecycle', 'platform_operations.view_data_lifecycle'),
        ('settings.manage_data_lifecycle', 'platform_operations.manage_data_lifecycle'),
        ('settings.export_data_lifecycle', 'platform_operations.export_data_lifecycle'),
    ):
        assert old in migration
        assert new in migration
        assert old not in defaults

    assert "module='operations'" in migration


def test_data_lifecycle_keeps_retention_engine_and_jobs_boundaries() -> None:
    service = read('app/platform_operations/data_lifecycle/service.py')
    retention_readme = read('app/retention/README.md')

    assert 'enqueue_canonical_job(' in service
    assert "job_type='data_lifecycle'" in service
    assert '.delay(' not in service
    assert '.apply_async(' not in service
    assert "action_url=url_for('jobs.executions')" in service
    assert 'Platform Operations → Data Lifecycle' in retention_readme
    assert 'archive-first' in retention_readme.lower()


def test_data_lifecycle_final_lock_is_release_gated() -> None:
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1_1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1_2.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_V1_2_AUDIT_2026_08_08.md').exists()
    assert 'verify_data_lifecycle_final_lock.py' in read('scripts/quality_gate.sh')

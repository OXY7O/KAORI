from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_platform_operations_overview_has_dedicated_owned_structure() -> None:
    assert (ROOT / 'app/platform_operations/overview/__init__.py').exists()
    assert (ROOT / 'app/platform_operations/overview/routes.py').exists()
    assert (ROOT / 'app/platform_operations/overview/presentation.py').exists()
    assert (ROOT / 'app/templates/platform_operations/overview/index.html').exists()

    platform_init = read('app/platform_operations/__init__.py')
    assert 'from app.platform_operations.overview import bp as overview_bp' in platform_init
    assert 'bp.register_blueprint(overview_bp)' in platform_init


def test_platform_operations_overview_is_permission_scoped_and_read_only() -> None:
    routes = read('app/platform_operations/overview/routes.py')
    template = read('app/templates/platform_operations/overview/index.html')

    assert '@any_permission_required(' in routes
    for permission in (
        'jobs.view',
        'platform_operations.view_data_lifecycle',
        'kubernetes_secrets.manage_reveal',
    ):
        assert permission in routes

    assert 'hx-post=' not in template
    assert '<form' not in template
    assert 'type="submit"' not in template
    assert 'role="tablist"' not in template


def test_platform_operations_overview_composes_authoritative_domain_projections() -> None:
    presentation = read('app/platform_operations/overview/presentation.py')
    lifecycle = read('app/platform_operations/data_lifecycle/presentation.py')
    kubernetes = read('app/platform_operations/kubernetes/presentation.py')
    kubernetes_routes = read('app/platform_operations/kubernetes/routes.py')

    assert 'build_job_execution_status_context()' in presentation
    assert 'build_data_lifecycle_overview_summary()' in presentation
    assert 'build_kubernetes_administration_summary()' in presentation

    assert 'def build_data_lifecycle_overview_summary()' in lifecycle
    assert 'DataLifecyclePolicy.query' in lifecycle
    assert 'ArchiveArtifact.query' in lifecycle
    assert "JobExecution.job_type == 'data_lifecycle'" in lifecycle

    assert 'def build_kubernetes_administration_summary()' in kubernetes
    assert 'Cluster.query' in kubernetes
    assert 'cluster_reveal_readiness' in kubernetes
    assert 'SecretRevealNamespacePolicy.query' in kubernetes
    assert '**build_kubernetes_administration_summary(),' in kubernetes_routes


def test_platform_operations_overview_stays_lightweight() -> None:
    overview = read('app/platform_operations/overview/presentation.py')
    lifecycle = read('app/platform_operations/data_lifecycle/presentation.py')
    lifecycle_summary = lifecycle.split('def build_data_lifecycle_overview_summary()', 1)[-1]

    for forbidden in (
        'inspect_celery_topology',
        'get_queue_readiness',
        'build_storage_profile',
        'preview_retention',
        'list_namespace',
        'read_namespace',
        'enqueue_canonical_job',
    ):
        assert forbidden not in overview

    for forbidden in ('build_storage_profile(', 'get_queue_readiness(', 'preview_retention('):
        assert forbidden not in lifecycle_summary


def test_platform_operations_overview_uses_kaori_page_components() -> None:
    template = read('app/templates/platform_operations/overview/index.html')

    for token in (
        'components/page_hero.html',
        'components/table_label.html',
        'components/operational_section_card.html',
        'components/section_link_button.html',
        'Operations Center',
        'Platform Posture',
        'Workspace Posture',
        'Operating Boundaries',
        'Read-only overview; changes stay in each workspace.',
        'table_label.status_indicator_label',
        'section_link_button.render',
    ):
        assert token in template


def test_platform_operations_overview_is_first_navigation_target() -> None:
    menu = read('app/templates/components/navigation/platform_operations_menu.html')
    breadcrumb = read('app/common/navigation.py')
    welcome = read('app/welcome/shortcuts.py')

    assert "url_for('platform_operations.overview.index')" in menu
    assert (
        menu.index('Overview')
        < menu.index('Jobs &amp; Executions')
        < menu.index('Data Lifecycle')
        < menu.index('Kubernetes Administration')
    )
    assert "endpoint.startswith('platform_operations.overview.')" in breadcrumb
    assert "('jobs.view', 'platform_operations.overview.index')" in welcome
    assert "('platform_operations.view_data_lifecycle', 'platform_operations.overview.index')" in welcome
    assert "('kubernetes_secrets.manage_reveal', 'platform_operations.overview.index')" in welcome


def test_platform_operations_overview_final_lock_is_release_gated() -> None:
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_OVERVIEW_LOCK_V1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_OVERVIEW_LOCK_V1_1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V2_0.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V2_2.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_OVERVIEW_FINAL_LOCK_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_OVERVIEW_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V2_0_AUDIT_2026_08_08.md').exists()
    quality_gate = read('scripts/quality_gate.sh')
    assert 'run_contract_migration_gate' in quality_gate
    assert "'Contract & Migration Safety'" in quality_gate
    assert 'tests/contracts' in quality_gate
    assert 'tests/migrations' in quality_gate
    assert "-m 'contract or migration'" in quality_gate
    assert 'verify_platform_operations_overview_final_lock.py' not in quality_gate


def test_platform_operations_overview_does_not_collapse_unknown_or_disabled_posture_to_ready() -> None:
    presentation = read('app/platform_operations/overview/presentation.py')

    assert 'unknown_workspace_count' in presentation
    assert 'review_workspace_count = attention_workspace_count + unknown_workspace_count' in presentation
    assert "overall_status_label, overall_status_tone = 'Configuration Review', 'unknown'" in presentation
    assert 'elif not global_enabled:' in presentation
    assert "status_label, status_tone = 'Global Gate Disabled', 'warning'" in presentation


def test_platform_operations_operating_boundaries_are_permission_scoped() -> None:
    template = read('app/templates/platform_operations/overview/index.html')
    presentation = read('app/platform_operations/overview/presentation.py')

    assert '<h1 class="{{ page_hero.title_classes() }}">Platform Overview</h1>' in template
    assert '{% for workspace in platform_overview.workspaces %}' in template
    assert '{{ workspace.boundary_title }}' in template
    assert '{{ workspace.boundary_description }}' in template
    assert 'Three platform controls, one shared operational model' not in template
    for title in ('Execution Evidence', 'Lifecycle Governance', 'Protected Administration'):
        assert title in presentation
        assert title not in template

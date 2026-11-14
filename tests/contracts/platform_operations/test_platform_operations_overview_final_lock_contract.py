from pathlib import Path

from jinja2 import Environment

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
    kubernetes_read_model = read('app/platform_operations/kubernetes/read_model.py')
    kubernetes_routes = read('app/platform_operations/kubernetes/routes.py')

    assert 'build_job_execution_status_context()' in presentation
    assert 'build_data_lifecycle_overview_summary()' in presentation
    assert 'build_kubernetes_administration_summary()' in presentation

    assert 'def build_data_lifecycle_overview_summary()' in lifecycle
    assert 'DataLifecyclePolicy.query' in lifecycle
    assert 'ArchiveArtifact.query' in lifecycle
    assert "JobExecution.job_type == 'data_lifecycle'" in lifecycle

    assert 'def build_kubernetes_administration_summary()' in kubernetes
    assert 'counts = administration_counts()' in kubernetes
    assert 'def administration_counts()' in kubernetes_read_model
    assert 'from app.models import Cluster, SecretRevealNamespacePolicy' in kubernetes_read_model
    assert 'Cluster.secret_reveal_encryption_verified.is_(True)' in kubernetes_read_model
    assert 'Cluster.secret_reveal_audit_verified.is_(True)' in kubernetes_read_model
    assert 'eligible_reveal_clusters' in kubernetes_read_model
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
        < menu.index('>Jobs</span>')
        < menu.index('Data Lifecycle')
        < menu.index('>Kubernetes Admin</span>')
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
    assert "status_label = str(kubernetes['administration_status_label'])" in presentation
    assert "status_tone = str(kubernetes['administration_status_tone'])" in presentation
    assert 'elif ready_count < cluster_count:' not in presentation


def test_platform_operations_operating_boundaries_are_permission_scoped() -> None:
    template = read('app/templates/platform_operations/overview/index.html')
    presentation = read('app/platform_operations/overview/presentation.py')

    assert "page_hero.intro('workflow', 'Operations Center', 'panels-top-left')" in template
    assert '<h1 class="{{ page_hero.title_classes() }}">Overview</h1>' in template
    assert '{% for workspace in platform_overview.workspaces %}' in template
    assert '{{ workspace.boundary_title }}' in template
    assert '{{ workspace.boundary_description }}' in template
    assert 'Three platform controls, one shared operational model' not in template
    for title in ('Execution Evidence', 'Lifecycle Governance', 'Protected Administration'):
        assert title in presentation
        assert title not in template


def test_platform_operations_workspace_description_is_compact_and_accessible() -> None:
    template = read('app/templates/platform_operations/overview/index.html')
    presentation = read('app/platform_operations/overview/presentation.py')

    assert 'class="min-w-0 truncate px-5 text-sm leading-6 text-content-secondary"' in template
    assert 'title="{{ workspace.description }}">{{ workspace.description }}</p>' in template
    assert "'description': 'Readiness and protected access controls.'" in presentation
    assert "'description': 'Protected Kubernetes controls with readiness and authorization gates.'" not in presentation
    assert 'lg:grid-cols-3' in template
    assert 'for workspace in platform_overview.workspaces' not in presentation


def test_workspace_posture_has_one_shared_guide_after_authoritative_status() -> None:
    template = read('app/templates/platform_operations/overview/index.html')
    Environment().parse(template)

    assert '{% import "components/info_tip.html" as info_tip %}' in template
    assert template.count("info_tip.render('operations-overview-workspace-posture-guide'") == 1
    assert template.count("variant='guide'") == 1
    assert 'header_badge=workspace_posture_context' in template

    posture = template.index('table_label.status_indicator_label(platform_overview.overall_status_label')
    guide = template.index("info_tip.render('operations-overview-workspace-posture-guide'")
    assert posture < guide < template.index('{% endset %}', guide)
    assert 'permission-scoped, committed operational signals' in template
    assert 'the Overview does not execute jobs' in template
    assert 'archive-first cleanup' in template
    assert 'Secret values stay in Secret Management' in template
    assert 'live access is verified at execution' in template


def test_operating_boundary_copy_is_compact_without_dropping_authority() -> None:
    template = read('app/templates/platform_operations/overview/index.html')
    presentation = read('app/platform_operations/overview/presentation.py')

    expected = (
        'Jobs owns queues, retries and execution evidence.',
        'Data Lifecycle owns retention and verified archives.',
        'Kubernetes governs readiness and reveal access.',
    )
    for copy in expected:
        assert f"'boundary_description': '{copy}'" in presentation
        assert len(copy) <= 55

    assert 'title="{{ workspace.boundary_description }}"' in template
    assert 'text-content-muted lg:truncate' in template
    assert '{{ workspace.boundary_description }}' in template
    assert '{% for workspace in platform_overview.workspaces %}' in template
    assert 'lg:grid-cols-3' in template
    assert 'hx-post=' not in template


def test_workspace_posture_metric_labels_are_compact_and_accessible() -> None:
    template = read('app/templates/platform_operations/overview/index.html')
    presentation = read('app/platform_operations/overview/presentation.py')
    Environment().parse(template)

    expected_labels = (
        ('Exec / Policy', 'Execution / Policy Alerts'),
        ('Archives / Jobs', 'Active Archives / Jobs'),
        ('Protected NS', 'Protected Namespaces'),
    )
    for short, full in expected_labels:
        assert f"'{short}'" in presentation
        assert f"'{full}'" in presentation
        assert len(short) <= 15

    assert 'for icon, label, value, full_label in workspace.metrics' in template
    assert 'title="{{ full_label }}"' in template
    assert '<span class="min-w-0 truncate" aria-hidden="true">{{ label }}</span>' in template
    assert '<span class="sr-only">{{ full_label }}</span>' in template
    assert 'grid grid-cols-3 divide-x divide-outline-subtle' in template
    assert 'for workspace in platform_overview.workspaces' in template

    # Preserve separate source-owned counts; never combine archive and job
    # activity or turn execution vs. policy attention into one total.
    assert "f'{attention} / {policy_attention}'" in presentation
    assert """f'{lifecycle["active_archive_total"]} / {lifecycle["active_job_total"]}'""" in presentation
    assert 'protected_namespaces' in presentation

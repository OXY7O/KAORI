from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / 'app/templates/integrations/jobs.html'
WORKSPACE = ROOT / 'app/templates/integrations/jobs/partials/_workspace.html'
ACTIVE = ROOT / 'app/templates/integrations/jobs/partials/_active_jobs.html'
QUEUES = ROOT / 'app/templates/integrations/jobs/partials/_queue_activity.html'
REGISTRY = ROOT / 'app/templates/integrations/jobs/partials/_registry.html'
PRESENTATION = ROOT / 'app/jobs/presentation.py'
README = ROOT / 'app/jobs/README.md'
SIDEBAR = ROOT / 'app/templates/components/navigation/sidebar.html'
INTEGRATIONS_MENU = ROOT / 'app/templates/components/navigation/integrations_menu.html'
OPERATIONS_MENU = ROOT / 'app/templates/components/navigation/platform_operations_menu.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_jobs_hero_uses_canonical_typography_and_compact_context_panel() -> None:
    page = read(PAGE)
    assert 'text-2xl font-semibold leading-tight tracking-tight' in page
    assert 'text-sm font-medium leading-6 text-brand-foreground-muted sm:text-base' in page
    assert 'mt-5 flex flex-wrap gap-2' in page
    assert page.count('page_hero.context_metric(') == 2
    assert 'page_hero.supporting_strip' not in page
    assert 'Monitor background work, progress, and execution outcomes across KAORI.' in page
    assert 'Background Work Status' in page
    assert 'page_hero.primary_action_classes()' in page
    assert 'Refresh Status' in page


def test_jobs_workspace_exposes_user_friendly_operational_views() -> None:
    workspace = read(WORKSPACE)
    assert 'Execution Overview' in workspace
    assert 'Active Work' in workspace
    assert 'Execution Registry' in workspace
    assert 'Queue Activity' in workspace
    assert 'Shared Execution' in workspace
    assert 'Queue Isolation' in workspace
    assert 'Lifecycle Managed' in workspace
    assert "setTab('active')" in workspace
    assert "setTab('registry')" in workspace
    assert "setTab('queues')" in workspace


def test_active_jobs_and_queue_activity_do_not_overclaim_worker_health() -> None:
    active = read(ACTIVE)
    queues = read(QUEUES)
    assert 'Follow queued, running, retrying, and cancellation-requested jobs.' in active
    assert 'xl:grid-cols-[minmax(0,2fr)_minmax(180px,1fr)_minmax(230px,1.25fr)_auto]' in active
    assert 'hx-trigger="every 5s"' in active
    assert 'Protected Run' in active
    assert 'Queue Activity reflects canonical job records.' in queues
    assert 'does not claim worker liveness' in queues


def test_job_rows_receive_workload_icons_and_queue_summaries() -> None:
    presentation = read(PRESENTATION)
    registry = read(REGISTRY)
    for icon in ('activity', 'scan-search', 'chart-no-axes-combined', 'chart-spline', 'workflow'):
        assert f"'{icon}'" in presentation
    assert "'icon': _JOB_ICONS.get" in presentation
    assert 'def _queue_activity' in presentation
    assert 'active_job_rows' in presentation
    assert 'job_queue_rows' in presentation
    assert 'data-lucide="{{ row.icon }}"' in registry


def test_jobs_navigation_is_platform_operations_not_integrations_submenu() -> None:
    sidebar = read(SIDEBAR)
    integrations = read(INTEGRATIONS_MENU)
    operations = read(OPERATIONS_MENU)
    assert 'Platform Operations' in sidebar
    assert 'platform_operations_menu.html' in sidebar
    assert 'Jobs &amp; Executions' not in integrations
    assert 'Jobs &amp; Executions' in operations
    assert "url_for('integrations.jobs')" in operations


def test_job_retention_boundary_is_documented_separately_from_activity_audit() -> None:
    text = read(README)
    assert 'Job records and Activity Audit records are different' in text
    assert 'separate `job_execution` domain' in text
    assert 'active jobs: never eligible' in text
    assert 'must not enable ad-hoc database deletion scripts' in text

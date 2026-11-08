from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[4]
TEMPLATES = ROOT / 'app' / 'templates' / 'platform_operations' / 'jobs' / 'executions'


def _read(relative_path: str) -> str:
    return (TEMPLATES / relative_path).read_text(encoding='utf-8')


def test_execution_overview_uses_integrated_workspace() -> None:
    source = _read('_workspace.html')

    assert 'Execution Overview' in source
    assert 'Execution Workspace' in source
    assert '{% set embedded = true %}' in source
    assert 'Active Work' in source
    assert 'Registry' in source
    assert 'Queues' in source
    assert 'rounded-2xl border border-brand-outline bg-kaori-soft/60' not in source


def test_registry_is_responsive_without_horizontal_table_scroll() -> None:
    source = _read('partials/_registry.html')

    assert 'lg:grid-cols-12' in source
    assert 'Search executions...' in source
    assert 'overflow-x-auto' not in source
    assert 'min-w-[940px]' not in source
    assert '<table' not in source
    assert 'table-fixed' not in source


def test_active_execution_progress_is_stable_and_compact() -> None:
    source = _read('partials/_active_jobs.html')

    assert 'progress_bar.job_progress' in source
    assert 'progress_bar.determinate' not in source
    assert 'hx-sync="this:replace"' in source
    assert 'notification-progress-indeterminate' not in source
    assert 'transition-[width]' not in source
    assert 'truncate' not in source


def test_queue_activity_uses_summary_strips_instead_of_nested_metric_cards() -> None:
    source = _read('partials/_queue_activity.html')

    assert 'grid grid-cols-2 gap-2 sm:grid-cols-4' in source
    assert 'Completed · 24H' in source
    assert 'Worker Readiness' in source
    assert "fragment='queues'" in source
    assert 'rounded-lg border border-outline-subtle bg-surface-card p-3' not in source


def test_changed_execution_templates_parse_and_follow_source_hygiene() -> None:
    environment = Environment()
    paths = [
        TEMPLATES / '_workspace.html',
        TEMPLATES / 'partials' / '_active_jobs.html',
        TEMPLATES / 'partials' / '_registry.html',
        TEMPLATES / 'partials' / '_queue_activity.html',
    ]

    for path in paths:
        source = path.read_text(encoding='utf-8')
        environment.parse(source)
        assert 'style=' not in source
        assert '<details' not in source
        assert '<summary' not in source
        import re

        assert re.search(r'#[0-9a-fA-F]{3,8}', source) is None


def test_htmx_fragments_remain_embedded_after_refresh() -> None:
    source = (ROOT / 'app' / 'platform_operations' / 'jobs' / 'routes.py').read_text(encoding='utf-8')

    assert "if fragment in {'active', 'registry', 'queues'}" in source
    assert "fragment_context['embedded'] = True" in source
    assert '**fragment_context' in source


def test_execution_tabs_use_titles_without_duplicate_count_badges() -> None:
    workspace = _read('_workspace.html')
    assert "('active', 'Active Work', 'activity', url_for('jobs.executions', execution_tab='active'))" in workspace
    assert "('registry', 'Registry', 'list-checks', url_for('jobs.executions', execution_tab='registry'))" in workspace
    assert "('queues', 'Queues', 'network', url_for('jobs.executions', execution_tab='queues'))" in workspace
    assert 'job_stats.active),' not in workspace.split('{% set execution_tabs = [', 1)[1].split('] %}', 1)[0]


def test_execution_sections_reuse_canonical_guide_and_registry_icon() -> None:
    for name, guide in (
        ('_active_jobs.html', 'jobs-active-work-guide'),
        ('_registry.html', 'jobs-execution-registry-guide'),
        ('_queue_activity.html', 'jobs-queue-activity-guide'),
    ):
        source = _read('partials/' + name)
        assert '{% import "components/info_tip.html" as info_tip %}' in source
        assert guide in source
        assert "variant='guide'" in source
    registry = _read('partials/_registry.html')
    assert 'data-lucide="list-checks" class="h-5 w-5"' in registry
    assert 'aria-hidden="true"' in registry

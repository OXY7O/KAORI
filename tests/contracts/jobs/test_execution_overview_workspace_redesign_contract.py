from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
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

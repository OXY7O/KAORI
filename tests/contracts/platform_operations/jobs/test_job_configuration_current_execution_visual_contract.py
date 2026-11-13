from pathlib import Path

from jinja2 import Environment

TEMPLATE = Path('app/templates/platform_operations/jobs/configuration/_execution_activity.html')


def test_current_execution_uses_visual_status_workspace():
    source = TEMPLATE.read_text(encoding='utf-8')
    assert 'Current Execution' in source
    assert 'bg-kaori-soft/40' in source
    assert 'progress_bar.job_progress' in source
    assert 'Ready for Execution' in source


def test_current_execution_keeps_single_determinate_progress_bar():
    source = TEMPLATE.read_text(encoding='utf-8')
    current_block = source.split('Current Execution', 1)[1].split('Manual runs use', 1)[0]
    assert current_block.count('progress_bar.job_progress') == 1
    assert 'progress_bar.determinate' not in current_block
    assert 'animate-pulse' not in current_block


def test_current_execution_metadata_remains_compact():
    source = TEMPLATE.read_text(encoding='utf-8')
    for label in ('Scope', 'Queue', 'Requested By', 'Started'):
        assert label in source
    assert 'lg:grid-cols-4' in source


def test_current_execution_idle_layout_uses_flexible_text_and_compact_badge() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    Environment().parse(source)

    assert "if active_job else 'lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center'" in source
    assert "'xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.95fr)] xl:items-center' if active_job" in source
    assert 'justify-self-start lg:self-center lg:justify-self-end' in source
    assert "status_indicator_label('Ready for Execution', 'normal')" in source
    assert 'title="{{ selected_job.execution_state.description }}"' in source
    assert 'title="{{ idle_execution_helper }}"' in source
    assert source.count('lg:truncate') >= 2
    assert 'min-w-0 text-sm font-semibold leading-6 text-content-primary lg:truncate' in source
    assert 'min-w-0 text-xs leading-5 text-content-muted lg:truncate' in source
    assert 'No active execution. The job is ready for its next scheduled or manual run.' in source
    assert 'No active execution. Manual dispatch is blocked until an eligible target is available.' in source
    assert 'whitespace-nowrap' not in source.split('Current Execution', 1)[1].split('Scope', 1)[0]

    # Active executions must keep their separate progress pane, process and detail evidence.
    assert 'progress_bar.job_progress(active_job' in source
    assert 'active_job.progress_process' in source
    assert 'active_job.progress_detail' in source
    assert 'selected_job.execution_disabled and selected_job.execution_blocker' in source


def test_registered_jobs_reuse_one_current_execution_owner() -> None:
    catalog = Path('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml').read_text(
        encoding='utf-8'
    )
    template_names = [
        line.split(':', 1)[1].strip()
        for line in catalog.splitlines()
        if line.strip().startswith('configuration_template:')
    ]
    assert len(template_names) >= 15

    base = Path('app/templates/platform_operations/jobs/configuration/definitions')
    for filename in set(template_names):
        source = (Path('app/templates') / filename).read_text(encoding='utf-8')
        if '_materialization_job.html' in source:
            source = (base / '_materialization_job.html').read_text(encoding='utf-8')
        assert '_execution_activity.html' in source, filename

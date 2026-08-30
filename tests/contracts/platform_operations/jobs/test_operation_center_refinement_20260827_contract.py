from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_execution_workspace_uses_capacity_analysis_content_tabs_and_live_fragments() -> None:
    workspace = read('app/templates/platform_operations/jobs/executions/_workspace.html')
    registry = read('app/templates/platform_operations/jobs/executions/partials/_registry.html')
    queues = read('app/templates/platform_operations/jobs/executions/partials/_queue_activity.html')

    assert 'components/content_tabs.html' in workspace
    assert 'content_tabs.render_links(' in workspace
    assert 'embedded=true' in workspace
    assert "data_namespace='execution'" in workspace
    assert "hx_indicator='#execution-workspace-loading'" in workspace
    assert 'components/framed_workspace_tabs.html' not in workspace
    assert 'hx-trigger="every 15s"' in registry
    assert 'hx-trigger="every 15s"' in queues
    assert 'document.hidden' in registry
    assert 'document.hidden' in queues
    assert 'hx-sync="this:replace"' in registry
    assert 'hx-sync="this:replace"' in queues


def test_registry_filters_are_one_row_and_details_use_shared_modal() -> None:
    registry = read('app/templates/platform_operations/jobs/executions/partials/_registry.html')

    assert "classes='grid gap-3 border-b" in registry
    assert 'lg:flex-nowrap' in registry
    assert registry.count('lg:basis-0 lg:flex-1') == 3
    assert 'components/resource_detail_modal.html' in registry
    assert 'resource_detail_modal.detail_button(' in registry
    assert 'resource_detail_modal.host(' in registry
    assert 'components/details/_expandable_row.html' not in registry


def test_current_execution_separates_process_and_detail() -> None:
    activity = read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')
    presentation = read('app/common/job_execution_presentation.py')

    assert '>Process<' in activity
    assert '>Detail<' in activity
    assert "'progress_process':" in presentation
    assert "'progress_detail':" in presentation


def test_data_lifecycle_history_refreshes_without_horizontal_scroll() -> None:
    index = read('app/templates/platform_operations/data_lifecycle/index.html')
    history = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')

    assert 'max-h-[580px]' not in index
    assert 'overflow-y-auto' not in index
    assert 'hx-trigger="every 20s"' in history
    assert 'overflow-x-auto' not in history
    assert "table_ui.table_classes('table-fixed')" in history
    assert 'min-w-[1120px]' not in history
    assert 'placeholder="Search archives..."' in history

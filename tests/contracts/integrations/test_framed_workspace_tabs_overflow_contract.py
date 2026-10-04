from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_framed_workspace_tabs_keep_overflow_horizontal_only() -> None:
    component = read('app/templates/components/framed_workspace_tabs.html')

    assert component.count('overflow-x-auto overflow-y-hidden') == 2
    assert component.count('class="flex w-max min-w-full gap-2 border-b border-outline-default"') == 2
    assert 'flex min-w-max gap-2 overflow-x-auto' not in component
    assert 'overflow-x-auto overflow-y-hidden border-b border-outline-default' not in component


def test_integration_workspaces_delegate_framed_tab_overflow_to_shared_owner() -> None:
    adapter = read('app/templates/components/integration_workspace_tabs.html')
    overview = read('app/templates/integrations/overview.html')

    assert 'framed_workspace_tabs.render(' in adapter
    assert 'framed_workspace_tabs.render_navigation(' in overview

    detail_templates = (
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html',
        'app/templates/integrations/observability/metrics_source/instance_detail.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_detail.html',
        'app/templates/integrations/storage/object_storage/providers/minio/instance_detail.html',
        'app/templates/integrations/registry/providers/harbor/instance_detail.html',
    )
    for relative in detail_templates:
        assert 'framed_workspace_tabs.render(' in read(relative), relative

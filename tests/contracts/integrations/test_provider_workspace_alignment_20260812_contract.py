from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_minio_configuration_reuses_canonical_operational_context() -> None:
    minio = read('app/templates/minio/partials/_detail_configuration.html')
    provider_contract = read('app/templates/integrations/components/_provider_configuration_contract.html')
    operational_context = read('app/templates/integrations/components/_provider_operational_context.html')

    assert 'provider_configuration_contract.render(' in minio
    assert 'Operational Boundary' not in minio
    assert 'Operational Flow' not in minio
    assert 'operational_context.render(' in provider_contract
    assert 'data-kaori-provider-operational-context' in operational_context
    assert 'Authority Boundary' in operational_context
    assert 'Step {{ loop.index }}' in operational_context


def test_provider_full_validation_uses_header_loading_bar_only() -> None:
    workspaces = {
        'prometheus': 'app/templates/prometheus/partials/_detail_validation_content.html',
        'alertmanager': 'app/templates/alertmanager/partials/_detail_validation_content.html',
        'minio': 'app/templates/minio/partials/_detail_validation.html',
    }

    for provider, workspace_path in workspaces.items():
        workspace = read(workspace_path)
        registry = read(f'app/templates/{provider}/partials/_capability_registry.html')

        assert (
            f"loading_id='{provider}-validation-loading'" in workspace
            or f'loading_id="{provider}-validation-loading"' in workspace
        )
        assert f'hx-indicator="#{provider}-validation-loading"' in workspace
        assert f'{provider}-capability-loading' in registry
        assert 'active=validation_job and validation_job.is_active' not in registry


def test_provider_tab_badges_are_safe_during_full_page_render() -> None:
    tabs = read('app/templates/components/framed_workspace_tabs.html')
    badge_macro = tabs.split('{% macro badge_oob', 1)[1]

    assert 'hx-swap-oob="innerHTML"' in badge_macro
    assert 'class="hidden"' in badge_macro
    assert 'hx-swap-oob="outerHTML"' not in badge_macro

    workspace_pairs = {
        'prometheus': (
            'app/templates/prometheus/partials/_detail_validation_content.html',
            'app/templates/prometheus/partials/_runtime_panel.html',
        ),
        'alertmanager': (
            'app/templates/alertmanager/partials/_detail_validation_content.html',
            'app/templates/alertmanager/partials/_runtime_panel.html',
        ),
        'minio': (
            'app/templates/minio/partials/_detail_validation.html',
            'app/templates/minio/partials/_detail_runtime.html',
        ),
    }
    for provider, (validation_path, runtime_path) in workspace_pairs.items():
        assert f'badge_oob("{provider}", "validation"' in read(validation_path)
        assert f'badge_oob("{provider}", "runtime"' in read(runtime_path)


def test_runtime_status_and_minio_lifecycle_follow_shared_provider_pattern() -> None:
    status = read('app/templates/integrations/components/_provider_job_status.html')
    assert 'data-kaori-provider-job-status' in status
    assert 'border-brand-outline bg-kaori-soft' in status

    runtime_paths = (
        'app/templates/integrations/kubernetes/partials/_runtime_workspace.html',
        'app/templates/prometheus/partials/_runtime_panel.html',
        'app/templates/alertmanager/partials/_runtime_panel.html',
        'app/templates/minio/partials/_detail_runtime.html',
    )
    for path in runtime_paths:
        runtime = read(path)
        assert '_provider_job_status.html' in runtime
        assert 'provider_job_status.render(' in runtime

    minio_lifecycle = read('app/templates/minio/partials/_detail_scope.html')
    assert 'data-kaori-inventory-lifecycle-v4' in minio_lifecycle
    assert 'data-kaori-inventory-lifecycle-v5' in minio_lifecycle
    assert 'data-kaori-inventory-lifecycle-decision' in minio_lifecycle
    assert 'KAORI Operational Consumers' in minio_lifecycle
    assert 'data-kaori-inventory-lifecycle-boundary' in minio_lifecycle
    assert 'include "minio/partials/_binding_registry.html"' in minio_lifecycle

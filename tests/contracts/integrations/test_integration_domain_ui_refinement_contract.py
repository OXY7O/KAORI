from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_domain_workspace_separates_tabs_from_registry_surface_and_preserves_readability() -> None:
    template = read('app/templates/integrations/domain.html')
    assert 'data-kaori-domain-registry-surface' in template
    assert 'overflow-x-auto rounded-xl border border-outline-subtle' in template
    assert 'min-w-[920px]' in template
    assert '[overflow-wrap:anywhere]' in template
    assert 'table-fixed' not in template


def test_operator_facing_prometheus_name_is_canonical() -> None:
    module = read('app/integrations/prometheus/__init__.py')
    service = read('app/integrations/service.py')
    detail = read('app/templates/prometheus/partials/_detail_configuration.html')
    form = read('app/templates/prometheus/instance_form.html')
    assert "runtime_label='Prometheus'" in module
    assert "'provider_label': 'Prometheus'" in service
    assert 'Prometheus / Thanos' not in module
    assert 'Prometheus / Thanos' not in service
    assert 'Thanos Query' not in detail
    assert 'Thanos Query' not in form


def test_loading_bars_are_operation_scoped() -> None:
    for provider in ('prometheus', 'alertmanager', 'minio'):
        registry = read(f'app/templates/{provider}/partials/_capability_registry.html')
        assert 'active=validation_job and validation_job.is_active' in registry
        assert 'hx-indicator="#{{ loading_id }}"' in registry or provider == 'minio'

        validation_name = '_detail_validation_content.html' if provider != 'minio' else '_detail_validation.html'
        validation = read(f'app/templates/{provider}/partials/{validation_name}')
        assert f'{provider}-validation-loading' not in validation
        assert f'hx-indicator="#{provider}-capability-loading"' in validation

def test_validation_and_runtime_refresh_tab_badges_oob() -> None:
    tabs = read('app/templates/components/framed_workspace_tabs.html')
    assert 'macro badge_oob' in tabs
    assert 'hx-swap-oob="innerHTML"' in tabs
    assert 'class="hidden"' in tabs
    assert 'hx-swap-oob="outerHTML"' not in tabs.split('macro badge_oob', 1)[1]

    for provider in ('prometheus', 'alertmanager', 'minio'):
        validation_name = '_detail_validation_content.html' if provider != 'minio' else '_detail_validation.html'
        runtime_name = '_runtime_panel.html' if provider != 'minio' else '_detail_runtime.html'
        validation = read(f'app/templates/{provider}/partials/{validation_name}')
        runtime = read(f'app/templates/{provider}/partials/{runtime_name}')

        assert f'badge_oob("{provider}", "validation"' in validation
        assert f'badge_oob("{provider}", "runtime"' in runtime

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_binding_validation_worker_imports_canonical_binding_model() -> None:
    tasks = read('app/integrations/validation/tasks.py')
    assert 'from app.models.integration import IntegrationBinding' in tasks
    assert 'db.session.get(IntegrationBinding, binding_id)' in tasks


def test_observability_validation_polling_is_terminal_aware() -> None:
    poller = read('app/templates/integrations/components/_validation_poller.html')
    state = read('app/integrations/validation/state.py')
    web = read('app/integrations/validation/web.py')
    workspace = read('app/integrations/observability/metrics_source/application/workspace_web.py')

    assert 'hx-trigger="every {{ delay }}"' in poller
    assert "'is_active': False if terminal" in state
    assert "'is_complete': True if terminal" in state
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in web
    assert "response.headers['HX-Trigger'] = '{\"kaori:notifications-changed\":{}}'" in web
    assert 'context.update(extra_context)' in workspace


def test_metrics_source_tabs_share_primary_header_typography() -> None:
    shared = read('app/templates/components/connection_validation_header.html')
    config = read('app/templates/integrations/components/_provider_configuration_contract.html')
    validation = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
    )
    runtime = read('app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html')
    scope = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')

    primary_title = 'text-base font-semibold text-content-primary'
    primary_description = 'mt-1 max-w-3xl text-sm leading-6 text-content-secondary'

    assert primary_title in shared
    assert primary_description in shared
    assert primary_title in config
    assert primary_description in config
    assert primary_title in scope
    assert 'max-w-3xl text-sm leading-6 text-content-secondary' in scope
    assert 'connection_validation_header.render(' in validation
    assert 'connection_validation_header.render(' in runtime
    assert 'mt-0.5 max-w-2xl text-xs leading-5 text-content-muted' not in shared

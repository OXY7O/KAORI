from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_HISTORY = ROOT / 'app/templates/integrations/partials/_runtime_history.html'
RUNTIME_WORKSPACE = (
    ROOT
    / 'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html'
)
KUBERNETES_DETAIL = (
    ROOT / 'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html'
)
REPOSITORY = ROOT / 'app/integrations/runtime/repository.py'
ROUTES = ROOT / 'app/integrations/routes.py'


def _text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_runtime_history_uses_kaori_one_line_htmx_filters_without_buttons():
    source = _text(RUNTIME_HISTORY)
    assert 'data-kaori-runtime-history-filters' in source
    assert 'table_ui.inventory_filter_bar_classes()' in source
    assert 'table_ui.filter_layout_classes()' in source
    assert 'lg:grid-cols-3' not in source
    assert 'hx-trigger="change delay:100ms"' in source
    assert 'name="history_trigger"' in source
    assert 'name="history_health"' in source
    assert 'name="history_readiness"' in source
    assert 'Apply Filters' not in source
    assert '>Reset<' not in source


def test_runtime_history_filters_are_server_side_and_persist_across_pagination():
    repository = _text(REPOSITORY)
    routes = _text(ROUTES)
    template = _text(RUNTIME_HISTORY)
    assert 'trigger_type: str' in repository
    assert 'health_status: str' in repository
    assert 'readiness: str' in repository
    assert 'IntegrationRuntimeObservation.trigger_type == trigger_filter' in repository
    assert 'IntegrationRuntimeObservation.health_status == health_filter' in repository
    assert 'IntegrationRuntimeObservation.readiness == readiness_filter' in repository
    assert "request.args.get('history_trigger'" in routes
    assert "request.args.get('history_health'" in routes
    assert "request.args.get('history_readiness'" in routes
    assert template.count("'history_trigger': selected_history_trigger") >= 3
    assert template.count("'history_health': selected_history_health") >= 3
    assert template.count("'history_readiness': selected_history_readiness") >= 3


def test_kubernetes_runtime_history_explicitly_enables_filters_in_full_and_partial_views():
    routes = _text(ROUTES)
    detail = _text(KUBERNETES_DETAIL)
    workspace = _text(RUNTIME_WORKSPACE)
    assert 'runtime_history_filters_enabled=True' in routes
    assert 'runtime_history_filters_enabled=true' in detail
    assert 'runtime_history_filters_enabled=true' in workspace


def test_runtime_primary_finding_replaces_duplicate_operational_focus_rows():
    source = _text(RUNTIME_WORKSPACE)
    assert 'data-kaori-runtime-primary-finding' in source
    assert 'Primary Finding' in source
    assert '{{ runtime_state.summary }}' in source
    assert 'Operational Focus' not in source
    assert 'data-kaori-operational-focus-list' not in source
    assert 'runtime_state.message' not in source


def test_changed_templates_parse_as_jinja():
    env = Environment()
    env.parse(_text(RUNTIME_HISTORY))
    env.parse(_text(RUNTIME_WORKSPACE))
    env.parse(_text(KUBERNETES_DETAIL))

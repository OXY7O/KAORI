from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_runtime_history_uses_inventory_table_primitives() -> None:
    template = read('app/templates/integrations/partials/_runtime_history.html')

    assert '{% import "components/table.html" as table_ui %}' in template
    assert "table_ui.table_classes('min-w-[78rem]')" in template
    assert 'table_ui.head_classes()' in template
    assert 'table_ui.header_cell_classes()' in template
    assert 'table_ui.header_cell_classes(action=true)' in template
    assert 'table_ui.row_classes()' in template
    assert 'table_ui.cell_classes()' in template
    assert 'table_ui.cell_classes(action=true)' in template
    assert 'data-kaori-runtime-history-table' in template
    assert '<thead class="{{ table_ui.head_classes() }}"' in template


def test_runtime_history_keeps_compact_context_and_shared_modal_detail() -> None:
    template = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'data-kaori-runtime-history-summary' in template
    assert 'data-kaori-runtime-history-posture-strip-v3' in template
    assert 'Observation Posture' in template
    assert 'record_actions.view_more(' in template
    assert "role='runtime-observation'" in template
    assert '>Observation</th>' in template
    assert '>Runtime Posture</th>' in template
    assert '>Health</th>' in template
    assert '>Capability Context</th>' in template
    assert '>State Change</th>' in template
    assert '>Details</th>' in template
    assert 'record_actions.view_more(' in template
    assert "role='runtime-observation'" in template
    assert 'runtime_observation_modal.render(' in template
    assert 'data-kaori-runtime-observation-detail' not in template


def test_runtime_history_uses_inventory_pagination_contract() -> None:
    template = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'pagination_ui.footer_classes()' in template
    assert 'pagination_ui.summary_group_classes()' in template
    assert 'pagination_ui.rows_group_classes()' in template
    assert 'pagination_ui.navigation_group_classes()' in template
    assert 'Runtime Observations</p>' in template
    assert '>Rows</label>' in template
    assert 'data-kaori-auto-submit' in template


def test_runtime_history_keeps_provider_neutral_routing() -> None:
    template = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'runtime_history_endpoint_name' in template
    assert 'runtime_history_detail_endpoint_name' in template
    assert 'runtime_history_route_args_value' in template
    assert "hx_swap='outerHTML'" in template

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_runtime_history_uses_kaori_standard_record_surface() -> None:
    template = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'data-kaori-runtime-history-standard-v2' in template
    assert 'data-kaori-runtime-history-summary' in template
    assert 'data-kaori-runtime-history-columns' in template
    assert 'data-kaori-runtime-history-records' in template
    assert 'Observed At' in template
    assert 'Runtime Posture' in template
    assert 'Health Score' in template
    assert 'Capability Profile' in template
    assert 'State Change' in template
    assert 'View More' in template
    assert 'hover:bg-kaori-mist' in template


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


def test_runtime_history_identity_icons_follow_kaori_violet() -> None:
    template = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'bg-kaori-soft text-kaori-primary-dark dark:text-kaori-accent' in template
    assert 'runtime_history_is_violet' not in template
    assert "runtime_history_variant|default('') == 'violet-v2'" not in template

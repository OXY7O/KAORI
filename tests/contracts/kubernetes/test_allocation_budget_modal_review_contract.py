"""UAT REVIEW: Allocation Budget is a full registry tab, not a per-cluster modal."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def test_allocation_budget_uses_full_canonical_table_in_query_backed_tab() -> None:
    parent = (ROOT / 'app/templates/kubernetes/tenant/partials/_capacity_governance.html').read_text(
        encoding='utf-8'
    )
    registry = (ROOT / 'app/templates/kubernetes/tenant/partials/_allocation_budget_registry.html').read_text(
        encoding='utf-8'
    )
    Environment(autoescape=True).parse(parent)
    Environment(autoescape=True).parse(registry)

    assert 'workspace_tabs.render_query_tabs(' in parent
    assert "active_allocation_view == 'budget'" in parent
    assert 'tenant-capacity-allocation-tabs' in parent
    assert '_allocation_budget_registry.html' in parent
    assert '_tenant_allocation_overview.html' in parent

    assert 'Allocation Budget' in registry
    assert 'table_ui.inventory_block_header(' in registry
    assert 'components/table_registry.html' in registry
    assert 'registry_ui.filter_form(' in registry
    assert 'registry_ui.clear_filters_link(' in registry
    assert 'registry_ui.footer(' in registry
    assert 'capacity-budget-registry' in registry
    assert 'capacity-budget-loading' in registry
    assert "table_ui.table_classes('min-w-[1000px] !table-fixed')" in registry
    assert 'rowspan="{{ visible_bars|length }}"' in registry
    assert 'capacity_budget_bars.get(item.cluster.id|string, [])' in registry
    assert 'item.snapshot_state' in registry
    for value in ('bar.budget', 'bar.committed', 'bar.headroom', 'bar.percent', 'bar.free_percent'):
        assert value in registry
    assert 'progress_bar.stacked_bar(bar.percent,' in registry
    assert 'Ratio unavailable' in registry
    assert 'Over budget by {{ bar.shortfall }}' in registry
    assert 'storage_bytes' in registry
    assert 'Storage is a logical admission ceiling' in registry

    for option in (
        'capacity_search',
        'capacity_environment',
        'capacity_state',
        'capacity_evidence',
        'capacity_resource',
    ):
        assert option in registry

    assert '<dialog' not in registry
    assert 'View More' not in registry
    assert 'hx-post' not in registry
    assert 'data-kaori-native-dialog' not in registry

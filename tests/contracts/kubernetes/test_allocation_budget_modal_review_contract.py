"""UAT review: Allocation Budget remains a canonical registry with expandable evidence."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / 'app/templates/kubernetes/tenant/partials'


def read(name: str) -> str:
    return (PARTIALS / name).read_text(encoding='utf-8')


def test_allocation_budget_uses_canonical_cluster_registry_and_expandable_detail() -> None:
    parent = read('_capacity_governance.html')
    registry = read('_allocation_budget_registry.html')
    detail = read('_allocation_budget_detail.html')
    overview = read('_tenant_allocation_overview.html')
    for template in (parent, registry, detail, overview):
        Environment(autoescape=True).parse(template)

    assert 'workspace_tabs.render_query_tabs(' in parent
    assert "active_allocation_view == 'budget'" in parent
    assert 'tenant-capacity-allocation-tabs' in parent
    assert '_allocation_budget_registry.html' in parent
    assert '_tenant_allocation_overview.html' in parent

    assert 'table_ui.inventory_block_header(' in registry
    assert 'components/table_registry.html' in registry
    assert 'components/details/_expandable_row.html' in registry
    assert 'registry_ui.filter_form(' in registry
    assert 'registry_ui.clear_filters_link(' in registry
    assert 'registry_ui.footer(' in registry
    assert 'capacity-budget-registry' in registry
    assert 'capacity-budget-loading' in registry
    assert 'detail_row.toggle_button(' in registry
    assert 'detail_row.static_detail_row(' in registry
    assert "table_ui.table_classes('min-w-[760px] table-fixed xl:min-w-0')" in registry
    assert "capacity_budget_bars.get(item.cluster.id|string, [])" in registry
    assert 'item.snapshot_state' in registry

    assert 'Committed Allocation Evidence' in detail
    for label in ('Budget', 'Committed', 'Headroom'):
        assert label in detail
    for value in ('bar.budget', 'bar.committed', 'bar.headroom', 'bar.percent', 'bar.free_percent'):
        assert value in detail
    assert 'progress_bar.stacked_bar(bar.percent,' in detail
    assert 'Ratio unavailable' in detail
    assert 'Over budget by {{ bar.shortfall }}' in detail
    assert 'storage_bytes' in detail
    assert 'Logical admission ceiling' in detail

    for option in (
        'capacity_search',
        'capacity_environment',
        'capacity_state',
        'capacity_evidence',
        'capacity_resource',
    ):
        assert option in registry

    assert 'data-dialog-target="{{ budget_guide_dialog_id }}"' in overview
    assert 'data-kaori-native-dialog' in overview
    assert 'View Contributions' in overview
    assert '<dialog' not in registry + detail
    assert 'hx-post' not in registry + detail
    assert 'View More' not in registry

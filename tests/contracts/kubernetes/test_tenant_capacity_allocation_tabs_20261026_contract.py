"""Tenant Capacity Governance UAT: query-backed Overview / Budget tabs and full registry."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / 'app/templates/kubernetes/tenant/partials'


def read(name: str) -> str:
    return (PARTIALS / name).read_text(encoding='utf-8')


def test_allocation_tabs_follow_membership_query_backed_navigation_standard() -> None:
    workspace = read('_capacity_governance.html')
    membership = read('_tenant_memberships_workspace.html')
    tabs = (ROOT / 'app/templates/components/workspace_tabs.html').read_text(encoding='utf-8')
    for source in (workspace, tabs):
        Environment(autoescape=True).parse(source)

    assert 'workspace_tabs.render_query_tabs(' in workspace
    assert 'workspace_tabs.render_query_tabs(' in membership
    assert 'tenant-capacity-allocation-tabs' in workspace
    assert 'hx-select="#tenant-capacity-allocation-tabs"' in workspace
    assert "active_allocation_view == 'budget'" in workspace
    assert "('overview', 'Tenant Allocation Overview'" in workspace
    assert "('budget', 'Allocation Budget'" in workspace
    assert '_tenant_allocation_overview.html' in workspace
    assert '_allocation_budget_registry.html' in workspace
    assert workspace.count('data-tenant-capacity-policy-form') == 1


def test_budget_shows_complete_committed_resource_table_not_a_detail_modal() -> None:
    registry = read('_allocation_budget_registry.html')
    overview = read('_tenant_allocation_overview.html')
    for source in (registry, overview):
        Environment(autoescape=True).parse(source)

    assert "table_ui.table_classes('min-w-[1000px] !table-fixed')" in registry
    assert 'table_ui.inventory_block_header(' in registry
    assert 'registry_ui.filter_form(' in registry
    assert 'registry_ui.clear_filters_link(' in registry
    assert 'registry_ui.footer(' in registry
    assert 'capacity_page' in registry
    assert 'capacity_per_page' in registry
    assert "capacity_budget_bars.get(item.cluster.id|string, [])" in registry
    assert "bars|selectattr('key', 'equalto', capacity_filters.resource)|list" in registry
    assert 'rowspan="{{ visible_bars|length }}"' in registry
    for label in ('Cluster / Evidence', 'Resource', 'Budget', 'Committed', 'Headroom', 'Allocation'):
        assert label in registry
    for field in ('bar.budget', 'bar.committed', 'bar.headroom', 'bar.shortfall', 'bar.percent'):
        assert field in registry
    assert "item.state != 'Unknown' and item.snapshot_state in ['current', 'fresh']" in registry
    assert "'Evidence Unavailable' if item.state == 'Unknown'" in registry
    assert 'Ratio unavailable' in registry
    assert 'progress_bar.stacked_bar(bar.percent,' in registry
    assert '<dialog' not in registry
    assert 'View More' not in registry
    assert 'hx-post' not in registry
    assert 'name="allocation_view" value="overview"' in overview


def test_budget_filters_are_server_backed_and_preserved_in_pagination() -> None:
    registry = read('_allocation_budget_registry.html')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

    for field in (
        'capacity_search',
        'capacity_environment',
        'capacity_state',
        'capacity_evidence',
        'capacity_resource',
    ):
        assert f'name="{field}"' in registry or f"'{field}': capacity_filters." in registry
        assert f"request.args.get('{field}')" in routes
    assert "context['capacity_filters'] = {" in routes
    assert "context['capacity_environment_options']" in routes
    assert "context['capacity_state_options']" in routes
    assert "context['capacity_evidence_options']" in routes
    assert "context['active_allocation_view'] = allocation_view" in routes
    assert "allocation_view not in {'overview', 'budget'}" in routes
    assert 'name="allocation_view" value="budget"' in registry
    assert 'name="allocation_cluster_id"' in registry
    assert 'capacity_query_params' in registry
    assert "query_params={'view': 'capacity', 'allocation_view': 'budget'" in registry
    assert "per_page_param='capacity_per_page'" in registry
    assert 'capacity_items, capacity_pagination = paginate_sequence(' in routes
    assert "capacity_rows = [item for item in capacity_rows if item['state'] == capacity_state]" in routes
    assert "allocation_view == 'overview' and selected is not None" in routes


def test_no_mutation_or_fabricated_headroom_in_budget_table() -> None:
    registry = read('_allocation_budget_registry.html')
    calculations = (ROOT / 'app/kubernetes/tenant/allocation_overview.py').read_text(encoding='utf-8')
    assert 'hx-post' not in registry
    assert 'method="post"' not in registry
    assert 'bar.known' in registry
    assert 'Ratio unavailable' in registry
    assert "bar.key == 'storage_bytes'" in registry
    assert 'Storage is a logical admission ceiling' in registry
    assert "state='Unknown' if key != 'storage_bytes' else 'Not Governed'" in calculations
    assert 'def build_tenant_allocation_bars(' in calculations

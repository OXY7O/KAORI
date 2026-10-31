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


def test_budget_cluster_registry_expands_reusable_resource_evidence() -> None:
    registry = read('_allocation_budget_registry.html')
    detail = read('_allocation_budget_detail.html')
    overview = read('_tenant_allocation_overview.html')
    for source in (registry, detail, overview):
        Environment(autoescape=True).parse(source)

    assert 'components/details/_expandable_row.html' in registry
    assert 'detail_row.toggle_button(' in registry
    assert 'detail_row.static_detail_row(' in registry
    assert "open_label='View Details'" in registry
    assert "close_label='Hide Details'" in registry
    assert 'detail_row.static_detail_row(detail_row_id, detail_target_id, 5' in registry
    assert '_allocation_budget_detail.html' in registry
    assert "table_ui.table_classes('min-w-[760px] table-fixed xl:min-w-0')" in registry
    for label in ('Cluster / Environment', 'Capacity State', 'Evidence', 'Namespaces', 'Actions'):
        assert label in registry
    assert 'capacity_budget_bars.get(item.cluster.id|string, [])' in registry
    assert "bars|selectattr('key', 'equalto', capacity_filters.resource)|list" in registry
    assert 'table_ui.cluster_identity(item.cluster.name, item.cluster.environment)' in registry
    assert 'item.committed_namespace_count' in registry
    assert 'rowspan=' not in registry
    assert 'min-w-[1000px]' not in registry
    assert 'registry_ui.filter_form(' in registry
    assert 'registry_ui.clear_filters_link(' in registry
    assert 'registry_ui.footer(' in registry

    assert 'Committed Allocation Evidence' in detail
    assert 'sm:grid-cols-2' in detail
    for field in ('bar.budget', 'bar.committed', 'bar.headroom', 'bar.shortfall', 'bar.percent'):
        assert field in detail
    assert "item.state != 'Unknown' and item.snapshot_state in ['current', 'fresh']" in detail
    assert 'Ratio unavailable' in detail
    assert 'progress_bar.stacked_bar(bar.percent,' in detail
    assert "bar.key == 'storage_bytes'" in detail
    assert 'No Matching Clusters' in registry
    assert 'hx-post' not in registry + detail
    assert 'name="allocation_view" value="overview"' in overview


def test_budget_how_it_works_uses_existing_native_dialog_beside_contributions() -> None:
    overview = read('_tenant_allocation_overview.html')
    assert 'data-dialog-target="{{ budget_guide_dialog_id }}"' in overview
    assert 'id="{{ budget_guide_dialog_id }}"' in overview
    assert 'data-kaori-native-dialog' in overview
    assert 'aria-labelledby="{{ budget_guide_dialog_id }}-title"' in overview
    assert 'data-kaori-dialog-close' in overview
    assert 'How allocation budgets work' in overview
    assert 'Request budget formula' in overview
    assert 'Logical storage policy' in overview
    assert 'ResourceQuota boundary' in overview
    assert overview.index('data-dialog-target="{{ budget_guide_dialog_id }}"') < overview.index(
        'data-dialog-target="{{ contributions_dialog_id }}"'
    )
    assert overview.index('data-dialog-target="{{ contributions_dialog_id }}"') < overview.index(
        'id="{{ budget_guide_dialog_id }}"'
    )
    assert '<details class="group rounded-xl border border-outline-subtle bg-surface-elevated">' not in overview


def test_admission_boundaries_use_compact_copy() -> None:
    workflow = read('_resource_profile_workflow.html')
    assert 'Capacity Governance verifies request budgets; Kubernetes enforces them.' in workflow
    assert 'Missing, stale or unbounded evidence blocks growth; reductions remain allowed.' in workflow


def test_budget_filters_are_server_backed_and_preserved_in_pagination() -> None:
    registry = read('_allocation_budget_registry.html')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
    capacity = (ROOT / 'app/kubernetes/tenant/allocation_overview.py').read_text(encoding='utf-8')

    assert 'build_resource_profile_capacity_workspace(context, active_view=active_view, args=request.args)' in routes
    for field in (
        'capacity_search',
        'capacity_environment',
        'capacity_state',
        'capacity_evidence',
        'capacity_resource',
    ):
        assert f'name="{field}"' in registry or f"'{field}': capacity_filters." in registry
        assert f"args.get('{field}')" in capacity
    assert "context['capacity_filters'] = filters" in capacity
    assert "context['capacity_environment_options']" in capacity
    assert "context['capacity_state_options']" in capacity
    assert "context['capacity_evidence_options']" in capacity
    assert "context['active_allocation_view'] = allocation_view" in capacity
    assert "allocation_view not in {'overview', 'budget'}" in capacity
    assert "capacity_resource not in {'', 'cpu', 'memory_bytes', 'pods', 'storage_bytes'}" in capacity
    assert 'name="allocation_view" value="budget"' in registry
    assert 'name="allocation_cluster_id"' in registry
    assert 'capacity_query_params' in registry
    assert "query_params={'view': 'capacity', 'allocation_view': 'budget'" in registry
    assert "per_page_param='capacity_per_page'" in registry
    assert 'capacity_items, capacity_pagination = paginate_sequence(' in capacity
    assert "capacity_rows = [item for item in capacity_rows if item['state'] == capacity_state]" in capacity
    assert "allocation_view == 'overview' and selected is not None" in capacity
    assert "page=args.get('capacity_page', 1, type=int) or 1" in capacity
    assert "per_page=args.get('capacity_per_page', 5, type=int) or 5" in capacity


def test_no_mutation_or_fabricated_headroom_in_budget_table() -> None:
    registry = read('_allocation_budget_registry.html')
    calculations = (ROOT / 'app/kubernetes/tenant/allocation_overview.py').read_text(encoding='utf-8')
    assert 'hx-post' not in registry
    assert 'method="post"' not in registry
    detail = read('_allocation_budget_detail.html')
    assert 'bar.known' in detail
    assert 'Ratio unavailable' in detail
    assert "bar.key == 'storage_bytes'" in detail
    assert 'Logical Storage is an admission ceiling' in detail
    assert "'state': 'Unknown' if key != 'storage_bytes' else 'Not Governed'" in calculations
    assert 'def build_tenant_allocation_bars(' in calculations

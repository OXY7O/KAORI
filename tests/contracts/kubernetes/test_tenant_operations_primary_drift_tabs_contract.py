"""Keep focused Tenant drift workflows at the primary Operations tab level."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / 'app/templates/kubernetes/tenant/partials'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_drift_workflows_use_canonical_primary_tabs_not_nested_tabs() -> None:
    operations = read('app/templates/kubernetes/tenant/operations.html')
    routes = read('app/kubernetes/tenant/routes.py')
    tab_helper = read('app/kubernetes/tenant/route_common.py')

    for key, label in (
        ('allocation-drift', 'Allocation Drift'),
        ('operational-reconcile', 'Operational Reconcile'),
    ):
        assert f"('{key}', '{label}'" in operations
        assert f"url_for('tenant.operations', tab='{key}')" in operations
        assert f"active_tab == '{key}'" in operations or f"active_tab in {{'{key}'" in routes
        assert f"'{key}'" in tab_helper

    assert operations.count('content_tabs.render_links(') == 1
    assert "'tenant-operations'" in operations
    assert "hx_target='#tenant-operations-workspace'" in operations
    assert "hx_push_url='true'" in operations
    assert "'tenant-drift-views'" not in operations
    assert 'data-tenant-drift-view' not in operations
    assert 'drift_view=drift_view' not in routes
    assert "active_tab in {'allocation-drift', 'operational-reconcile'}" in routes


def test_existing_drift_urls_still_map_to_primary_tabs() -> None:
    route_common = read('app/kubernetes/tenant/route_common.py')
    assert "if active_tab == 'drift-reconcile':" in route_common
    assert "request.args.get('drift_view') == 'operations'" in route_common
    assert "return 'operational-reconcile' if" in route_common
    assert "else 'allocation-drift'" in route_common


def test_each_primary_tab_has_two_tables_with_provider_details_preserved() -> None:
    operations = read('app/templates/kubernetes/tenant/operations.html')
    allocation = operations.split("{% elif active_tab == 'allocation-drift' %}", 1)[1].split(
        "{% elif active_tab == 'operational-reconcile' %}", 1
    )[0]
    operational = operations.split("{% elif active_tab == 'operational-reconcile' %}", 1)[1].split('{% else %}', 1)[0]

    assert allocation.count('{% include "kubernetes/tenant/partials/') == 2
    for name in ('_capsule_tenant_quota_drift.html', '_capsule_shared_allocation_drift.html'):
        assert name in allocation
    assert operational.count('{% include "kubernetes/tenant/partials/') == 3
    assert '_operations_drift_registry.html' in operational
    assert '_operations_access_reconciliation_registry.html' in operational
    assert '<details class="group' in operational
    assert 'data-tenant-provider-authority-disclosure' in operational
    assert '_operations_provider_registry.html' in operational


def test_each_registry_keeps_primary_tab_through_pagination_filter_and_clear() -> None:
    for name, tab in (
        ('_capsule_tenant_quota_drift.html', 'allocation-drift'),
        ('_capsule_shared_allocation_drift.html', 'allocation-drift'),
        ('_operations_drift_registry.html', 'operational-reconcile'),
        ('_operations_access_reconciliation_registry.html', 'operational-reconcile'),
        ('_operations_provider_registry.html', 'operational-reconcile'),
    ):
        source = (PARTIALS / name).read_text(encoding='utf-8')
        assert "'tab': '" + tab + "'" in source, name
        assert 'registry_ui.footer(' in source, name
        assert '.total_items > 0' not in source, name
        assert "'drift_view':" not in source, name
        if tab == 'operational-reconcile':
            assert f'name="tab" value="{tab}"' in source
            assert f"query_params={{'tab': '{tab}'}}" in source


def test_both_capsule_drift_registries_use_full_kaori_table_contract() -> None:
    """#2931: canonical header/filter/columns/detail/empty/footer for both Capsule authorities."""
    from jinja2 import Environment

    specs = (
        (
            '_capsule_tenant_quota_drift.html',
            'capsule-tenant-quota-drift',
            'capsule_tenant_quota_drifted',
            'capsule_tenant_quota_filters',
            'ops_capsule_tenant_quota',
            'tenant.reapply_capsule_tenant_quota_route',
            'tenant.accept_capsule_tenant_provider_state_route',
        ),
        (
            '_capsule_shared_allocation_drift.html',
            'capsule-shared-allocation-drift',
            'capsule_shared_drift_intents',
            'capsule_shared_drift_filters',
            'ops_capsule_shared',
            'tenant.reapply_capsule_shared_allocation_route',
            'tenant.accept_capsule_shared_provider_allocation_route',
        ),
    )
    for filename, registry_id, rows, filters, query_key, reapply, accept in specs:
        source = read('app/templates/kubernetes/tenant/partials/' + filename)
        Environment().parse(source)
        assert 'components/table.html' in source
        assert 'components/table_registry.html' in source
        assert "table_ui.inventory_block_header(" in source
        assert 'result_count=' in source
        assert "header_actions=header_actions" in source
        assert 'registry_ui.clear_filters_link(' in source
        assert 'registry_ui.filter_form(' in source
        assert "aria_label='Filter " in source
        assert 'table_ui.inventory_filter_bar_classes()' in source
        assert 'table_ui.filter_select_classes()' in source
        assert 'table_ui.search_field(' in source
        assert query_key + '_tenant_id' in source
        assert query_key + '_search' in source
        assert filters + '.tenant_id' in source
        assert filters + '.search' in source
        assert "name=\"tab\" value=\"allocation-drift\"" in source
        assert "min-w-[880px] !table-fixed' if " + rows + " else '!table-fixed'" in source
        assert 'min-w-[1450px]' not in source
        assert 'min-w-[840px]' not in source
        for header in ('Tenant', 'Provider / Authority', 'Status', 'Allocation Difference', 'Details'):
            assert '>' + header + '</th>' in source
        assert 'colspan="5"' in source
        assert "table_label.status_label('Drifted', 'warning')" in source
        assert 'first.kaori_value' in source and 'first.provider_value' in source
        assert 'data-kaori-native-dialog' in source
        assert 'data-kaori-dialog-open' in source
        assert 'data-dialog-target="{{ dialog_id }}"' in source
        assert 'aria-haspopup="dialog"' in source
        assert 'data-kaori-dialog-close' in source
        assert 'View More' in source
        assert 'Provider Evidence' in source
        assert 'Reconciliation Decision' in source
        assert 'difference.kaori_value' in source
        assert 'difference.provider_value' in source
        assert "source.get('uid')" in source
        assert "source.get('resource_version')" in source
        assert "drift.get('observed_at')" in source
        assert "state.get('blocked_reason')" in source
        assert "table_label.special_label('Control Unavailable'" in source
        assert "can_manage and state.get('reapply_supported') and state.get('accept_supported')" in source
        assert source.count('<form method="post"') == 2
        assert source.count('name="csrf_token" value="{{ csrf_token() }}"') == 2
        assert "url_for('" + reapply + "'" in source
        assert "url_for('" + accept + "'" in source
        assert source.count('data-kaori-dialog-close') == 2
        assert "registry_ui.footer('tenant.operations'" in source
        assert "'tab': 'allocation-drift'" in source
        assert 'components/states/_empty_state.html' in source
        assert '§rid§' not in source


def test_capsule_drift_filters_are_committed_and_independently_paginated() -> None:
    routes = read('app/kubernetes/tenant/routes.py')
    quota = read('app/kubernetes/tenant/capsule_tenant_quota_governance.py')
    shared = read('app/kubernetes/tenant/capsule_allocation_governance.py')
    for name in (
        'ops_capsule_tenant_quota_tenant_id',
        'ops_capsule_tenant_quota_search',
        'ops_capsule_shared_tenant_id',
        'ops_capsule_shared_search',
    ):
        assert "request.args.get('" + name + "')" in routes
    assert "'capsule_tenant_quota_filters':" in quota
    assert "'capsule_shared_drift_filters':" in shared
    for source in (quota, shared):
        assert "str(drift_tenant_id or '').strip()" in source
        assert "str(drift_search or '').strip()[:160]" in source
        assert "normalized_search.casefold()" in source
        assert "paginate_sequence(" in source
    assert "tenant.provider_reference" in quota
    assert "intent.resource_name" in shared
    # UI gets already-committed rows, no new request-time direct provider read.
    for template in ('_capsule_tenant_quota_drift.html', '_capsule_shared_allocation_drift.html'):
        source = read('app/templates/kubernetes/tenant/partials/' + template)
        assert 'build_client(' not in source
        assert 'requests.get(' not in source

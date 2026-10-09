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

    assert operations.count("content_tabs.render_links(") == 1
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
    operational = operations.split("{% elif active_tab == 'operational-reconcile' %}", 1)[1].split(
        "{% else %}", 1
    )[0]

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

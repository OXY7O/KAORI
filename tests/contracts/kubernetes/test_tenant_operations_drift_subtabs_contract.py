"""Lock focused Tenant Drift & Reconcile navigation without losing provider evidence."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / 'app/templates/kubernetes/tenant/partials'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_drift_subtabs_use_shared_url_owned_navigation() -> None:
    operations = read('app/templates/kubernetes/tenant/operations.html')
    routes = read('app/kubernetes/tenant/routes.py')

    assert "('allocation', 'Allocation Drift', 'layers-3'" in operations
    assert "('operations', 'Operational Reconcile', 'git-compare-arrows'" in operations
    assert "content_tabs.render_links(" in operations
    assert "'tenant-drift-views'" in operations
    assert "hx_target='#tenant-operations-workspace'" in operations
    assert "hx_push_url='true'" in operations
    assert 'data-tenant-drift-view="{{ drift_view }}"' in operations
    assert "requested_drift_view if requested_drift_view in {'allocation', 'operations'}" in routes
    assert 'drift_view=drift_view,' in routes


def test_two_primary_tables_per_subtab_with_provider_authority_preserved() -> None:
    operations = read('app/templates/kubernetes/tenant/operations.html')
    allocation = operations.split("{% if drift_view == 'allocation' %}", 1)[1].split(
        '{% else %}', 1
    )[0]
    operational = operations.split('id="tenant-drift-operations"', 1)[1].split(
        '{% endif %}', 1
    )[0]

    assert allocation.count('{% include "kubernetes/tenant/partials/') == 2
    for name in ('_capsule_tenant_quota_drift.html', '_capsule_shared_allocation_drift.html'):
        assert name in allocation

    assert '_operations_drift_registry.html' in operational
    assert '_operations_access_reconciliation_registry.html' in operational
    assert 'data-tenant-provider-authority-disclosure' in operational
    assert '<details class="group' in operational
    assert '_operations_provider_registry.html' in operational


def test_each_registry_keeps_subtab_scope_when_paginating_filtering_and_clearing() -> None:
    for filename, view in (
        ('_capsule_tenant_quota_drift.html', 'allocation'),
        ('_capsule_shared_allocation_drift.html', 'allocation'),
        ('_operations_drift_registry.html', 'operations'),
        ('_operations_access_reconciliation_registry.html', 'operations'),
        ('_operations_provider_registry.html', 'operations'),
    ):
        content = (PARTIALS / filename).read_text(encoding='utf-8')
        assert "'drift_view': '" + view + "'" in content, filename
        assert 'registry_ui.footer(' in content, filename
        assert ".total_items > 0" not in content, filename
        if view == 'operations':
            assert 'name="drift_view" value="operations"' in content, filename
            assert "query_params={'tab': 'drift-reconcile', 'drift_view': 'operations'}" in content

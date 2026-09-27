from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_overview_reuses_canonical_inventory_sync_authority() -> None:
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
    workspace = (ROOT / 'app/kubernetes/tenant/workspace.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')

    assert "def get_tenant_overview_context(" in workspace
    assert "get_inventory_freshness_context" in workspace
    assert "kubernetes.inventory.sync" in workspace
    assert "@tenant_bp.post('/inventory-sync')" in routes
    assert "@permission_required('clusters.sync')" in routes
    assert "job_key='kubernetes.inventory.sync'" in routes
    assert "trigger_type='manual'" in routes
    assert "tenant.inventory_sync" in template
    assert "Sync Now" in template
    assert "Reconcile" not in template


def test_tenant_overview_has_multicluster_inventory_and_capacity_hierarchy() -> None:
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')

    for label in (
        'Tenant Estate',
        'Cluster Coverage & Allocation',
        'Tenant Distribution',
        'Inventory Data Snapshot',
        'Access Attention',
        'Governance Posture',
    ):
        assert label in template

    assert 'Quick Actions' not in template
    assert 'tenant_overview_clusters' in template
    assert 'tenant_inventory_snapshot' in template
    assert 'Committed Allocation' in template
    assert 'Tenant Allocation Budget' in template
    assert 'Actual Utilization' not in template


def test_tenant_overview_uses_shared_kaori_section_and_metric_components() -> None:
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')

    assert 'components/operational_section_card.html' in template
    assert 'components/resource_posture_grid.html' in template
    assert 'components/action_button.html' in template
    assert 'components/table_label.html' in template
    assert 'operational_section_card.render' in template
    assert 'resource_posture_grid.render' in template


def test_tenant_hero_identity_is_non_redundant() -> None:
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

    assert "page_hero.intro(tenant_page_icon, 'Kubernetes Tenant', tenant_page_icon)" in base
    assert "tenant_page_title='Overview'" in routes
    assert 'Kubernetes Tenant Overview' not in base

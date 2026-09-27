from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_overview_owns_registered_worker_sync_without_provider_mutation() -> None:
    registry = (ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml').read_text(
        encoding='utf-8'
    )
    config = (ROOT / 'app/config/default.py').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
    overview = (ROOT / 'app/kubernetes/tenant/overview.py').read_text(encoding='utf-8')
    adapter = (ROOT / 'app/kubernetes/tenant/job_adapter.py').read_text(encoding='utf-8')
    task = (ROOT / 'app/kubernetes/tenant/tasks.py').read_text(encoding='utf-8')
    sync_service = (ROOT / 'app/kubernetes/tenant/sync_service.py').read_text(encoding='utf-8')

    assert 'key: kubernetes.tenant.sync' in registry
    assert 'queue_name: inventory' in registry
    assert 'default_interval_minutes: 60' in registry
    assert 'app.kubernetes.tenant.tasks' in config
    assert 'app.kubernetes.tenant.tasks.sync_tenant_inventory' in config
    assert "TENANT_SYNC_JOB_KEY = 'kubernetes.tenant.sync'" in adapter
    assert 'enqueue_canonical_job(' in adapter
    assert "@shared_task(" in task
    assert "name='app.kubernetes.tenant.tasks.sync_tenant_inventory'" in task
    assert 'build_tenant_inventory_snapshot' in sync_service
    assert 'NamespaceInventory' in sync_service
    assert 'TenantNamespace' in sync_service
    assert 'reconcile_' not in sync_service

    assert "@tenant_bp.post('/inventory-sync')" in routes
    assert "@permission_required('tenant.manage')" in routes
    assert 'dispatch_tenant_inventory_sync' in routes
    assert "_INVENTORY_JOB_KEY = 'kubernetes.tenant.sync'" in overview
    assert 'job_key=_INVENTORY_JOB_KEY' in overview
    assert "trigger_type='manual'" in overview


def test_sync_all_inventory_includes_tenant_domain() -> None:
    routes = (ROOT / 'app/platform_operations/jobs/routes.py').read_text(encoding='utf-8')

    assert "job_keys.append('kubernetes.inventory.sync')" in routes
    assert "job_keys.append('kubernetes.tenant.sync')" in routes
    assert "job_keys.append('object_storage.inventory.sync')" in routes
    assert "current_user.has_permission('tenant.manage')" in routes


def test_tenant_overview_uses_tls_style_collection_snapshot_and_contextual_sync_actions() -> None:
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')
    live_state = (ROOT / 'app/templates/kubernetes/tenant/partials/_sync_live_state.html').read_text(
        encoding='utf-8'
    )

    assert 'components/snapshot_context_bar.html' in template
    assert "title='Tenant Collection Snapshot'" in template
    assert 'Tenant Inventory Operations' in live_state
    assert 'Automatic Sync' in live_state
    assert 'Last Successful' in live_state
    assert 'Next Scheduled' in live_state
    assert 'Sync Tenant' in template
    assert 'Configure Sync' in template
    assert 'Sync All Inventory' in template
    assert "job_key='kubernetes.tenant.sync'" in template
    assert 'tenant.inventory_sync' in template
    assert 'Quick Actions' not in template
    assert 'Add Tenant' not in template
    assert 'Resource Profiles' not in template
    assert 'Provision Namespace' not in template


def test_tenant_overview_redesigns_multicluster_posture_and_unknown_capacity_state() -> None:
    workspace = (ROOT / 'app/kubernetes/tenant/workspace.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')

    for label in (
        'Tenant Estate',
        'Multi-Cluster Posture',
        'Tenant Estate by Cluster',
        'Committed Snapshot Coverage',
        'Tenant Capacity Governance',
        'Capacity Evidence Unavailable',
    ):
        assert label in template

    assert "'capacity_available': capacity_available" in workspace
    assert "{% if row.capacity_available %}" in template
    assert 'Tenant sync does not fabricate or replace Capacity Analytics evidence.' in template
    assert 'CPU N/A' not in template
    assert 'Memory N/A' not in template
    assert 'Actual Utilization' not in template


def test_operational_attention_is_prioritized_not_three_equal_cards() -> None:
    workspace = (ROOT / 'app/kubernetes/tenant/workspace.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')

    assert 'Needs Attention' in template
    assert 'Recent Tenant Activity' in template
    assert 'tenant_attention_rows' in workspace
    assert 'tenant_recent_activity_rows' in workspace
    assert 'Access Attention' not in template
    assert 'Governance Posture' not in template
    assert 'Recent Tenant Changes' not in template
    assert 'xl:grid-cols-3' not in template


def test_tenant_overview_uses_shared_kaori_components() -> None:
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')

    assert 'components/operational_section_card.html' in template
    assert 'components/resource_posture_grid.html' in template
    assert 'components/action_button.html' in template
    assert 'components/table_label.html' in template
    assert 'components/snapshot_context_bar.html' in template
    assert 'operational_section_card.render' in template
    assert 'resource_posture_grid.render' in template
    assert 'snapshot_context.render' in template


def test_tenant_hero_identity_is_non_redundant() -> None:
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

    assert "page_hero.intro(tenant_page_icon, 'Kubernetes Tenant', tenant_page_icon)" in base
    assert "tenant_page_title='Overview'" in routes
    assert 'Kubernetes Tenant Overview' not in base

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
    assert '@shared_task(' in task
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


def test_sync_all_inventory_includes_tenant_domain_but_not_overview_button() -> None:
    jobs_routes = (ROOT / 'app/platform_operations/jobs/routes.py').read_text(encoding='utf-8')
    overview = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')
    sync_workspace = (ROOT / 'app/templates/kubernetes/tenant/partials/_sync_workspace.html').read_text(
        encoding='utf-8'
    )

    assert "job_keys.append('kubernetes.inventory.sync')" in jobs_routes
    assert "job_keys.append('kubernetes.tenant.sync')" in jobs_routes
    assert "job_keys.append('object_storage.inventory.sync')" in jobs_routes
    assert "current_user.has_permission('tenant.manage')" in jobs_routes
    assert 'Sync All Inventory' not in overview
    assert 'Sync All Inventory' not in sync_workspace


def test_tenant_sync_matches_tls_background_behavior() -> None:
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
    task = (ROOT / 'app/kubernetes/tenant/tasks.py').read_text(encoding='utf-8')
    sync_workspace = (ROOT / 'app/templates/kubernetes/tenant/partials/_sync_workspace.html').read_text(
        encoding='utf-8'
    )
    live_state = (ROOT / 'app/templates/kubernetes/tenant/partials/_sync_live_state.html').read_text(
        encoding='utf-8'
    )

    assert 'hx-post="{{ url_for(\'tenant.inventory_sync\') }}"' in sync_workspace
    assert 'hx-target="#tenant-sync-workspace"' in sync_workspace
    assert 'tenantInventorySyncFinished from:body' in sync_workspace
    assert 'hx-trigger="every 1s"' in live_state
    assert "'tenantInventorySyncFinished': True" in routes
    assert "'kaori:notifications-changed': True" in routes
    assert "if is_htmx:" in routes
    assert 'queue_transient_feedback(' in routes
    assert 'create_notification(' in task
    assert "'Tenant Sync Completed'" in task
    assert "'Tenant Sync Completed With Exceptions'" in task
    assert "notification_deck_user_ids" in task


def test_tenant_overview_uses_tls_style_collection_snapshot_and_contextual_sync_actions() -> None:
    overview = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')
    sync_workspace = (ROOT / 'app/templates/kubernetes/tenant/partials/_sync_workspace.html').read_text(
        encoding='utf-8'
    )
    live_state = (ROOT / 'app/templates/kubernetes/tenant/partials/_sync_live_state.html').read_text(
        encoding='utf-8'
    )

    assert 'kubernetes/tenant/partials/_sync_workspace.html' in overview
    assert 'components/snapshot_context_bar.html' in sync_workspace
    assert "title='Tenant Collection Snapshot'" in sync_workspace
    assert "latest_supporting='Source: '" in sync_workspace
    assert 'Tenant Inventory Operations' in live_state
    assert 'Automatic Sync' in live_state
    assert 'Last Successful' in live_state
    assert 'Next Scheduled' in live_state
    assert 'Sync Tenant' in sync_workspace
    assert 'Configure Sync' in sync_workspace
    assert "job_key='kubernetes.tenant.sync'" in sync_workspace
    assert 'tenant.inventory_sync' in sync_workspace
    assert 'Quick Actions' not in overview
    assert 'Add Tenant' not in overview
    assert 'Resource Profiles' not in overview
    assert 'Provision Namespace' not in overview


def test_tenant_overview_keeps_multicluster_posture_compact() -> None:
    workspace = (ROOT / 'app/kubernetes/tenant/workspace.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')

    for label in (
        'Multi-Cluster Posture',
        'Tenant Estate by Cluster',
        'Tenant Estate',
        'Snapshot',
        'Capacity',
        'Open Cluster Inventory',
    ):
        assert label in template

    assert 'visible_cluster_rows = cluster_rows[:5]' in workspace
    assert "'tenant_overview_cluster_hidden'" in workspace
    assert 'Showing {{ tenant_overview_clusters|length }} of {{ tenant_overview_cluster_total }}' in template
    assert 'Committed Allocation' not in template
    assert 'Allocation Budget' not in template
    assert 'Remaining Headroom' not in template
    assert 'Capacity Evidence Unavailable' not in template
    assert 'Capacity data stale' in template
    assert 'Open Capacity' in template
    assert 'CPU N/A' not in template
    assert 'Memory N/A' not in template
    assert 'Actual Utilization' not in template


def test_operational_attention_is_bounded_and_recent_activity_is_not_forced_equal_height() -> None:
    workspace = (ROOT / 'app/kubernetes/tenant/workspace.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')

    assert 'Needs Attention' in template
    assert 'Recent Tenant Activity' in template
    assert 'limit: int = 3' in workspace
    assert 'tenant_attention_rows' in workspace
    assert 'tenant_recent_activity_rows' in workspace
    assert 'Recent Tenant, access, and credential changes.' in template
    assert "extra_classes='h-full'" not in template
    assert 'xl:items-start' in template
    assert 'Access Attention' not in template
    assert 'Governance Posture' not in template
    assert 'Recent Tenant Changes' not in template


def test_tenant_overview_uses_shared_kaori_components() -> None:
    overview = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')
    sync_workspace = (ROOT / 'app/templates/kubernetes/tenant/partials/_sync_workspace.html').read_text(
        encoding='utf-8'
    )

    assert 'components/operational_section_card.html' in overview
    assert 'components/resource_posture_grid.html' in overview
    assert 'components/table_label.html' in overview
    assert 'operational_section_card.render' in overview
    assert 'resource_posture_grid.render' in overview
    assert 'components/action_button.html' in sync_workspace
    assert 'components/snapshot_context_bar.html' in sync_workspace
    assert 'snapshot_context.render' in sync_workspace


def test_tenant_hero_identity_is_non_redundant() -> None:
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

    assert "page_hero.intro(tenant_page_icon, 'Kubernetes Tenant', tenant_page_icon)" in base
    assert "tenant_page_title='Overview'" in routes
    assert 'Kubernetes Tenant Overview' not in base

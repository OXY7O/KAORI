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


def test_tenant_sync_workspace_context_is_constructed_from_sync_state() -> None:
    workspace = (ROOT / 'app/kubernetes/tenant/workspace.py').read_text(encoding='utf-8')

    assert "def get_tenant_sync_workspace_context() -> dict[str, Any]:" in workspace
    assert "'tenant_collection_snapshot': _tenant_collection_snapshot(sync_state)" in workspace
    assert "'tenant_sync_state': sync_state" in workspace
    broken_helper = """def get_tenant_sync_workspace_context() -> dict[str, Any]:
    sync_state = build_tenant_sync_state()
    return {
        **sync_context,
    }"""
    assert broken_helper not in workspace


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


def test_tenant_overview_keeps_multicluster_posture_compact_and_canonical() -> None:
    workspace = (ROOT / 'app/kubernetes/tenant/workspace.py').read_text(encoding='utf-8')
    overview = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')
    cluster_estate = (ROOT / 'app/templates/kubernetes/tenant/partials/_cluster_estate.html').read_text(
        encoding='utf-8'
    )
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

    assert 'Multi-Cluster Posture' in overview
    assert 'kubernetes/tenant/partials/_cluster_estate.html' in overview
    assert 'components/table.html' in cluster_estate
    assert 'components/pagination.html' in cluster_estate
    assert "table_ui.table_classes('min-w-[900px]')" in cluster_estate
    assert 'table_ui.cluster_identity(row.name, row.environment)' in cluster_estate
    assert 'pagination_ui.footer_classes()' in cluster_estate
    assert 'pagination.allowed_per_page' in cluster_estate
    assert "hx-get="{{ url_for('tenant.cluster_estate') }}"" in cluster_estate
    assert "endpoint='tenant.cluster_estate'" in cluster_estate
    assert "href_endpoint='tenant.index'" in cluster_estate
    assert "def get_tenant_cluster_estate_context(*, page: int = 1, per_page: int = 5)" in workspace
    assert 'paginate_sequence(' in workspace
    assert "@tenant_bp.get('/overview/cluster-estate')" in routes
    assert 'Committed Allocation' not in cluster_estate
    assert 'Allocation Budget' not in cluster_estate
    assert 'Remaining Headroom' not in cluster_estate
    assert 'Capacity Evidence Unavailable' not in cluster_estate
    assert 'Open Capacity' in cluster_estate
    assert 'CPU N/A' not in cluster_estate
    assert 'Memory N/A' not in cluster_estate
    assert 'Actual Utilization' not in cluster_estate


def test_operational_attention_is_bounded_and_recent_activity_is_richer() -> None:
    workspace = (ROOT / 'app/kubernetes/tenant/workspace.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')

    assert 'Needs Attention' in template
    assert 'Recent Tenant Activity' in template
    assert 'limit: int = 3' in workspace
    assert 'tenant_attention_rows' in workspace
    assert 'tenant_recent_activity_rows' in workspace
    assert "'kind': 'Tenant'" in workspace
    assert "'kind': 'Access'" in workspace
    assert "'kind': 'Credential'" in workspace
    assert "'status': lifecycle" in workspace
    assert 'Latest committed Tenant lifecycle changes.' in template
    assert '{{ item.kind }}' in template
    assert 'table_label.status_label(item.status, item.tone)' in template
    assert 'Showing {{ tenant_recent_activity_rows|length }} latest committed event' in template
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
    cluster_estate = (ROOT / 'app/templates/kubernetes/tenant/partials/_cluster_estate.html').read_text(
        encoding='utf-8'
    )

    assert 'components/table_label.html' in overview
    assert 'operational_section_card.render' in overview
    assert 'resource_posture_grid.render' in overview
    assert 'components/table.html' in cluster_estate
    assert 'components/pagination.html' in cluster_estate
    assert 'components/action_button.html' in sync_workspace
    assert 'components/snapshot_context_bar.html' in sync_workspace
    assert 'snapshot_context.render' in sync_workspace


def test_tenant_hero_identity_is_non_redundant() -> None:
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

    assert "page_hero.intro(tenant_page_icon, 'Kubernetes Tenant', tenant_page_icon)" in base
    assert "tenant_page_title='Overview'" in routes
    assert 'Kubernetes Tenant Overview' not in base

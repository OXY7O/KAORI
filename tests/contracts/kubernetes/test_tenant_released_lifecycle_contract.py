from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_released_generation_is_not_decommissioned_or_deleted_in_provider() -> None:
    model = read('app/models/tenant.py')
    migration = read('migrations/versions/20261009_tenant_released.py')
    release = read('app/kubernetes/tenant/release_preflight.py')
    discovery = read('app/kubernetes/tenant/discovery_service.py')
    adoption = read('app/kubernetes/tenant/discovery_adoption.py')
    route = read('app/kubernetes/tenant/routes.py')
    ui = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')

    assert "RELEASED = 'released'" in model
    assert "'decommissioned', 'released'" in model
    assert "'deprovisioned', 'released'" in model
    assert "down_revision = '20261004_registry_analytics'" in migration
    assert "ck_tenants_lifecycle_status" in migration
    assert "ck_tenant_namespaces_provisioning_status" in migration
    assert "Cannot downgrade while Released" in migration

    assert 'def release_adopted_tenant_committed(' in release
    assert "previous.get('status') != 'handoff_review_required'" in release
    assert 'review_tenant_release_preflight_committed(' in release
    assert 'with_for_update()' in release
    assert "provider_mutation_performed') is not False" in release
    assert "if age < 0 or age > 900" in release
    assert 'new_objects != old_objects' in release
    assert 'TenantLifecycleStatus.RELEASED.value' in release
    assert 'TenantNamespaceProvisioningStatus.RELEASED.value' in release
    assert "'provider_resource_deleted': False" in release
    assert "'rbac_mutation_performed': False" in release
    assert 'delete_namespace(' not in release
    assert 'delete_cluster_custom_object(' not in release
    assert 'patch_cluster_custom_object(' not in release

    assert "TenantLifecycleStatus.RELEASED.value" in discovery
    assert "TenantNamespaceProvisioningStatus.RELEASED.value" in discovery
    assert 'def _released_predecessor_evidence(' in adoption
    assert "provider_uid != str(evidence.get('provider_uid')" in adoption
    assert "'re_adoption_lineage'" in adoption

    assert "@tenant_bp.post('/tenants/<string:tenant_id>/release-governance')" in route
    assert "@permission_required('integrations.manage')" in route
    assert "request.form.get('confirm_release_governance') != 'approved'" in route
    assert "release_adopted_tenant_committed(" in route
    assert 'tenant.release_tenant_governance_route' in ui
    assert 'name="confirm_release_governance"' in ui
    assert "'Released · Provider Retained'" in ui


def test_released_history_is_excluded_from_active_counters_and_discovery() -> None:
    context = read('app/kubernetes/tenant/registry_context.py')
    summary = read('app/kubernetes/tenant/admin_workspace.py')
    discovery = read('app/kubernetes/tenant/discovery_service.py')

    assert 'TenantLifecycleStatus.RELEASED.value' in context
    assert 'TenantNamespaceProvisioningStatus.RELEASED.value' in context
    assert "'decommissioned', 'released'" in summary
    assert "'deprovisioned', 'released'" in summary
    assert "('deprovisioned', 'released')" in discovery
    assert "('decommissioned', 'released')" in discovery

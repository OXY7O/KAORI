from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_native_external_access_observer_has_explicit_read_only_authority() -> None:
    service = read('app/kubernetes/tenant/external_native_access_observation.py')
    routes = read('app/kubernetes/tenant/routes_access.py')
    context = read('app/kubernetes/tenant/access_service.py')
    ui = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')

    assert 'def observe_external_native_access_committed(' in service
    assert "tenant.provider_key != 'native_kubernetes'" in service
    assert "tenant.reconciliation_authority != 'native_kubernetes'" in service
    assert "tenant.lifecycle_status != 'ready'" in service
    assert "TenantNamespace.provisioning_status == 'ready'" in service
    assert "core.read_namespace(record.namespace" in service
    assert "rbac.list_namespaced_role_binding(" in service
    assert "_MAX_NAMESPACES = 30" in service
    assert "_MAX_BINDINGS = 200" in service
    assert "'effective_rbac_verified': False" in service
    assert "'identity_import_performed': False" in service
    assert "'rbac_mutation_performed': False" in service
    assert "'secret_material_persisted': False" in service
    assert "target_type=_TARGET" in service
    assert "db.session.commit()" in service
    assert "create_namespaced_role_binding(" not in service
    assert "patch_namespaced_role_binding(" not in service
    assert "delete_namespaced_role_binding(" not in service

    assert "@tenant_bp.post('/external-access/observe-native')" in routes
    assert 'def observe_native_external_access_route():' in routes
    assert "@permission_required('tenant.manage')" in routes
    assert "_csrf()" in routes
    assert "observe_external_native_access_committed(" in routes
    assert "external_native_tenants" in context
    assert "recent_external_native_access" in context
    assert "data-external-native-access-inventory" in ui
    assert "tenant.observe_native_external_access_route" in ui
    assert 'name="csrf_token"' in ui
    assert 'name="tenant_id"' in ui
    assert "binding.ownership" in ui
    assert "binding.claimed_grant_marker" in ui
    assert "Labels indicate possible correlation" in ui


def test_native_access_observation_reuses_capsule_workspace_without_duplicate_new_surface() -> None:
    ui = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    assert workspace.count('_external_capsule_access_inventory.html') == 1
    assert ui.count('data-external-native-access-inventory') == 1
    assert ui.count('External Capsule Access Inventory') == 1
    assert ui.count('Native Namespace RBAC Inventory') == 1
    assert ui.count('method="post"') >= 2

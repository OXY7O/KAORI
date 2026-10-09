from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_external_access_inspection_reuses_tenant_workspaces_and_never_autogrants():
    observation = read('app/kubernetes/tenant/external_access_observation.py')
    route = read('app/kubernetes/tenant/routes_access.py')
    service = read('app/kubernetes/tenant/access_service.py')
    ui = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')

    assert "tenant.provider_key != 'capsule'" in observation
    assert "'v1beta2' not in snapshot.tenant_api_versions" in observation
    assert "source_uid != expected_uid" in observation
    assert "AuditEvent.query.filter_by(target_type=_TARGET" in observation
    assert "'rbac_mutation_performed': False" in observation
    assert "'identity_import_performed': False" in observation
    assert "get_cluster_custom_object(" in observation
    assert 'patch_cluster_custom_object(' not in observation
    assert 'create_access_grant_committed(' not in observation
    assert 'add_user_membership_committed(' not in observation

    assert "@tenant_bp.post('/external-access/observe')" in route
    assert "@permission_required('tenant.manage')" in route
    assert '_csrf()' in route
    assert 'observe_external_capsule_access_committed(' in route
    assert "return _tenant_section_redirect('access-grants')" in route

    assert "'recent_external_capsule_access'" in service
    assert "'external_capsule_tenants'" in service
    assert ".limit(5).all()" in service
    assert '_external_capsule_access_inventory.html' in workspace
    assert 'Inspect External Access' in ui
    assert 'role.permissions_sha256' not in ui
    assert 'name="csrf_token"' in ui
    assert 'name="tenant_id"' in ui
    assert 'No membership or RBAC mutation' in ui or 'does not import IdP users' in ui

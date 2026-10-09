from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_release_preflight_is_non_destructive_and_separate_from_decommission():
    source = read('app/kubernetes/tenant/release_preflight.py')
    route = read('app/kubernetes/tenant/routes.py')
    context = read('app/kubernetes/tenant/registry_context.py')
    ui = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')

    assert "tenant.ownership_status != 'adopted'" in source
    assert "_active_credential_count(tenant_id)" in source
    assert "_active_grant_count(tenant_id)" in source
    assert "resource_profile_id is not None" in source
    assert "get_cluster_custom_object(" in source
    assert "read_namespace(" in source
    assert "latest_external_capsule_access_evidence(tenant_id)" in source
    assert "'release_executed': False" in source
    assert "'release_execution_available': False" in source
    assert "'provider_resource_deleted': False" in source
    assert "'provider_rbac_modified': False" in source
    assert "db.session.add(AuditEvent(" in source
    assert "delete_namespace(" not in source
    assert "delete_cluster_custom_object(" not in source
    assert "revoke_access_grant_committed(" not in source

    assert "@tenant_bp.post('/tenants/<string:tenant_id>/release-preflight')" in route
    assert "review_tenant_release_preflight_committed(" in route
    assert "_csrf()" in route
    assert "review_tenant_release_route" in ui
    assert "Review Release" in ui
    assert "No current dependency blockers, but Release execution is not yet admitted." in ui
    assert "release_evidence" in context
    assert "latest_ids.c.id" in context

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_native_foreign_role_equivalence_is_review_only_and_provider_authoritative():
    service = (ROOT / 'app/kubernetes/tenant/external_access_profile_equivalence.py').read_text()
    routes = (ROOT / 'app/kubernetes/tenant/routes_access.py').read_text()
    template = (ROOT / 'app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html').read_text()
    context = (ROOT / 'app/kubernetes/tenant/access_service.py').read_text()
    assert "'import_authorized': False" in service
    assert "'effective_rbac_verified': False" in service
    assert "'identity_verified': False" in service
    assert "read_namespaced_role_binding(" in service
    assert "read_namespaced_role(" in service
    assert "read_cluster_role(" in service
    assert "_role_rules_signature(" in service
    assert "review_native_external_role_profile_committed(" in routes
    assert "name=\"binding_uid\"" in template
    assert "Review Profile Match" in template
    assert "recent_external_access_profile_reviews" in context
    for token in (
        'patch_namespaced_role(', 'patch_namespaced_role_binding(',
        'create_namespaced_role_binding(', 'create_access_grant_committed(',
        'release_adopted_tenant_committed(', 'delete_namespaced_role_binding(',
    ):
        assert token not in service

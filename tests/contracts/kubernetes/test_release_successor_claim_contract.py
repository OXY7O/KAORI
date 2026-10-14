from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_successor_reference_remains_non_authoritative_and_authorized():
    service = (ROOT / 'app/kubernetes/tenant/release_successor_claim.py').read_text()
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text()
    detail = (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html').read_text()
    context = (ROOT / 'app/kubernetes/tenant/registry_context.py').read_text()
    assert "'external_reference_unverified'" in service
    assert "'external_successor_verified': False" in service
    assert "'provider_handoff_verified': False" in service
    assert "'release_authorized': False" in service
    assert 'review_tenant_release_preflight_committed' in service
    assert 'with_for_update()' in service
    assert 'release-handoff/successor-reference' in routes
    assert "@permission_required('integrations.manage')" in routes
    assert 'confirm_successor_reference' in detail
    assert "url_for('tenant.record_tenant_release_successor_reference_route'" in detail
    assert 'External Reference Unverified' in detail
    assert "'kubernetes_tenant_release_successor_claim'" in context
    for forbidden in (
        'patch_namespace(',
        'patch_namespaced_resource_quota(',
        'delete_namespace(',
        'release_adopted_tenant_committed(',
        'reconcile_access_grant_committed(',
    ):
        assert forbidden not in service

"""The approved Native Tenant Release cycle preserves provider and approval authority."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_canonical_native_handoff_release_handback_are_separate_explicit_routes():
    routes = source('app/kubernetes/tenant/routes.py')
    html = source('app/templates/kubernetes/tenant/partials/_tenant_management_detail.html')
    assert "def accept_native_successor_handoff_route(" in routes
    assert "def execute_native_release_handoff_route(" in routes
    assert "def finalize_verified_native_release_route(" in routes
    assert "def verify_native_successor_handback_route(" in routes
    assert "@permission_required('clusters.manage')" in routes
    assert 'confirm_native_handoff_execution' in html
    assert 'confirm_native_release_finalization' in html
    assert 'confirm_successor_handback' in html
    assert 'csrf_token()' in html
    assert 'Finalize Verified Native Release' in html
    assert 'Verify Provider &amp; Hand Back as Platform Admin' in html
    assert 'kubernetes_successor_token' not in html


def test_native_cycle_services_are_provider_preserving_and_fail_closed():
    executor = source('app/kubernetes/tenant/native_handoff_executor.py')
    finalizer = source('app/kubernetes/tenant/release_preflight.py')
    handback = source('app/kubernetes/tenant/native_successor_handback.py')
    discovery = source('app/kubernetes/tenant/discovery_adoption.py')
    scope = source('app/kubernetes/tenant/native_platform_admin_authority.py')
    assert 'verify_native_provider_admin_authority(' in executor
    assert 'require_current_native_acceptance(' in executor
    assert 'verify_external_native_component(' in executor
    assert "'status': 'in_progress'" in executor
    assert "'partial_handoff_recovery_required'" in executor
    assert 'release_verified_native_tenant_committed(' in finalizer
    assert "'release_mode': 'managed_handoff'" in finalizer
    assert 'TenantLifecycleStatus.RELEASED.value' in finalizer
    assert 'TenantNamespaceProvisioningStatus.RELEASED.value' in finalizer
    assert 'handback_native_successor_governance_committed(' in handback
    assert "require_platform_admin_actor(" in handback
    assert "'adoption_automatic': False" in handback
    assert "'handback_governance'" in discovery
    assert 'resource_version=resource_version' in discovery
    assert 'V1SelfSubjectReview(' in scope
    assert 'V1SelfSubjectAccessReviewSpec(' in scope
    for snippet in ('delete_namespace(', 'delete_namespaced_resource_quota(',
                    'delete_namespaced_limit_range(', 'create_namespace('):
        assert snippet not in executor
        assert snippet not in handback
    assert "release_adopted_tenant_committed(" not in executor


def test_normal_registry_is_committed_only_and_does_not_hold_bearer():
    registry = source('app/kubernetes/tenant/registry_context.py')
    acceptance = source('app/kubernetes/tenant/native_successor_acceptance.py')
    handback = source('app/kubernetes/tenant/native_successor_handback.py')
    assert "'kubernetes_tenant_release_verified_successor_acceptance'" in registry
    assert "'kubernetes_tenant_release_native_handoff_execution'" in registry
    assert "'kubernetes_tenant_verified_native_successor_handback'" in registry
    assert 'runtime_adapter.build_client(' not in registry
    assert "'secret_material_persisted': False" in acceptance
    assert "'secret_material_persisted': False" in handback

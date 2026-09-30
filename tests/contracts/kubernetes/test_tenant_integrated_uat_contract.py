from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_tenant_workspace_uses_only_approved_sidebar_destinations() -> None:
    menu = _read('app/templates/components/navigation/tenant_menu.html')
    for endpoint, label in (
        ('tenant.index', 'Overview'),
        ('tenant.tenants', 'Tenants'),
        ('tenant.resource_profiles', 'Resource Profiles'),
        ('tenant.namespace_provisioning', 'Namespace Provisioning'),
        ('tenant.operations', 'Operations'),
    ):
        assert f"url_for('{endpoint}')" in menu
        assert f'>{label}</span>' in menu


def test_tenant_workspace_reads_committed_cross_child_state() -> None:
    workspace = _read('app/kubernetes/tenant/workspace.py')

    for model_name in (
        'TenantCredential',
        'TenantManagedResourceIntent',
        'TenantDomainReservation',
        'TenantExposurePolicy',
        'TenantAuditEvidence',
        'TenantAdvancedCapabilityIntent',
    ):
        assert model_name in workspace

    assert "get_active_recommendation_findings(domain='kubernetes')" in workspace
    assert 'build_namespace_access_package' in workspace
    assert "startswith('kubernetes.tenant.')" in workspace


def test_tenant_tenants_surface_exposes_governed_access_and_credential_lifecycle_without_secrets() -> None:
    routes = _read('app/kubernetes/tenant/routes.py')
    page = _read('app/templates/kubernetes/tenant/tenants.html')
    admin = _read('app/templates/kubernetes/tenant/partials/_tenant_admin_workspace.html')
    memberships = _read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    grants = _read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    credential = _read('app/templates/kubernetes/tenant/partials/_tenant_credentials_workspace.html')
    namespace_access = _read('app/templates/kubernetes/tenant/partials/_tenant_namespace_access_workspace.html')
    membership_registry = _read('app/templates/kubernetes/tenant/partials/_membership_registry.html')
    group_registry = _read('app/templates/kubernetes/tenant/partials/_group_registry.html')
    access_grant_registry = _read('app/templates/kubernetes/tenant/partials/_access_grant_registry.html')
    credential_registry = _read('app/templates/kubernetes/tenant/partials/_credential_registry.html')
    namespace_access_registry = _read('app/templates/kubernetes/tenant/partials/_namespace_access_registry.html')
    template = (
        page
        + admin
        + memberships
        + grants
        + credential
        + namespace_access
        + membership_registry
        + group_registry
        + access_grant_registry
        + credential_registry
        + namespace_access_registry
    )

    for path in (
        '/credentials/human',
        '/credentials/deployer',
        '/credentials/<int:credential_id>/renew',
        '/credentials/<int:credential_id>/suspend',
        '/credentials/<int:credential_id>/resume',
        '/credentials/<int:credential_id>/revoke',
    ):
        assert f"@tenant_bp.post('{path}')" in routes

    assert 'Memberships' in template
    assert 'Access Grants' in template
    assert 'Issue Human Access' in template
    assert 'Issue CI/CD Deployer' in template
    assert 'Namespace Access' in template
    assert 'service_account_name' in template
    assert 'renewal_due_at' in template
    assert 'valid_until' in template
    assert 'approved_access_methods' in template
    assert 'credential.token' not in template
    assert 'credential.kubeconfig' not in template


def test_tenant_operations_keeps_provider_policy_audit_and_reports_evidence_explicit() -> None:
    overview = _read('app/templates/kubernetes/tenant/overview.html')
    operations = _read('app/templates/kubernetes/tenant/operations.html')
    provider = _read('app/templates/kubernetes/tenant/partials/_operations_provider_registry.html')
    access = _read('app/templates/kubernetes/tenant/partials/_operations_access_reconciliation_registry.html')
    evidence = _read('app/templates/kubernetes/tenant/partials/_operations_evidence_registry.html')

    assert 'provider_state' in provider
    assert 'reconciliation_authority' in provider
    assert 'reconciliation_status' in access
    assert 'correlation_status' in evidence
    assert 'managed-resource' in evidence
    assert 'domain-reservation' in evidence
    assert 'exposure-policy' in evidence
    assert 'Tenant Governance' in overview
    assert 'Governance &amp; Reports' in operations
    assert 'Reports' in operations


def test_tenant_operations_uses_shared_content_tabs_without_sidebar_third_level() -> None:
    menu = _read('app/templates/components/navigation/tenant_menu.html')
    operations = _read('app/templates/kubernetes/tenant/operations.html')

    assert 'components/content_tabs.html' in operations
    assert 'content_tabs.render_links' in operations
    for label in ('Provisioning', 'Runs & Evidence', 'Drift & Reconcile', 'Activity'):
        assert label in operations
        assert f'>{label}</span>' not in menu



def test_tenant_adoption_preflight_is_compact_and_pvc_bounds_are_explicit() -> None:
    modal = _read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')
    tenants = _read('app/templates/kubernetes/tenant/tenants.html')

    assert 'max-w-5xl' in modal
    assert 'max-w-[1240px]' not in modal
    assert 'Min PVC Size' in modal
    assert 'Max PVC Size' in modal
    assert 'Not declared' in modal
    assert "pvc_min is not none and pvc_min != ''" in modal
    assert "pvc_max is not none and pvc_max != ''" in modal
    assert 'Active principals' in tenants
    assert 'Active user, group, and machine principals' not in tenants

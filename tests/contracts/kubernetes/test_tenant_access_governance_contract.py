from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_access_governance_keeps_application_and_kubernetes_rbac_separate() -> None:
    model_source = (ROOT / 'app/models/tenant.py').read_text(encoding='utf-8')
    access_source = (ROOT / 'app/kubernetes/tenant/access.py').read_text(encoding='utf-8')
    reconciliation_source = (ROOT / 'app/kubernetes/tenant/access_reconciliation.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260926_tenant_access_grants.py').read_text(encoding='utf-8')
    architecture = (ROOT / 'docs/architecture/kubernetes-tenant-access-governance.md').read_text(encoding='utf-8')
    rbac_architecture = (ROOT / 'docs/rbac/RBAC_ARCHITECTURE.md').read_text(encoding='utf-8')

    for model in ('TenantGroup', 'TenantMembership', 'TenantAccessGrant'):
        assert f'class {model}(db.Model):' in model_source

    for profile in ("'viewer'", "'operator'", "'tenant_admin'", "'deployer'"):
        assert profile in access_source

    assert 'ClusterRoleBinding' not in reconciliation_source
    assert 'RbacAuthorizationV1Api' in (
        ROOT / 'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/client.py'
    ).read_text(encoding='utf-8')
    assert "down_revision = '20260925_tenant_capacity'" in migration
    assert 'KAORI application RBAC and Tenant Kubernetes RBAC are separate authorization layers.' in architecture
    assert 'They do not extend `User.has_permission()`' in rbac_architecture


def test_tenant_access_profiles_forbid_wildcard_and_platform_scope() -> None:
    access_source = (ROOT / 'app/kubernetes/tenant/access.py').read_text(encoding='utf-8')
    assert "'clusterrolebindings'" in access_source
    assert "'clusterroles'" in access_source
    assert "'namespaces'" in access_source
    assert "'resourcequotas'" in access_source
    assert "'rolebindings'" in access_source
    assert "'roles'" in access_source
    assert "if '*' in rule.api_groups or '*' in rule.verbs" in access_source


def test_tenant_access_revocation_records_effective_removal_evidence() -> None:
    service_source = (ROOT / 'app/kubernetes/tenant/access_service.py').read_text(encoding='utf-8')
    reconciliation_source = (ROOT / 'app/kubernetes/tenant/access_reconciliation.py').read_text(encoding='utf-8')
    assert 'tenant_access_grant.revoked' in service_source
    assert 'provider access removal requires attention' in service_source
    assert '_delete_binding(api, grant, namespace)' in reconciliation_source
    assert 'Revoked Tenant Access Grant still has effective RoleBinding state.' in reconciliation_source

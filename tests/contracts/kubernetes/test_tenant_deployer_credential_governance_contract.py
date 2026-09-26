from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_deployer_credentials_extend_canonical_tenant_credential_domain() -> None:
    model = (ROOT / 'app/models/tenant.py').read_text(encoding='utf-8')
    policy = (ROOT / 'app/kubernetes/tenant/credential.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/credential_service.py').read_text(encoding='utf-8')

    assert "SERVICE_ACCOUNT = 'service_account'" in model
    assert "DEPLOYER_SERVICE_ACCOUNT = 'deployer_service_account'" in model
    assert "CICD_KUBECONFIG = 'cicd_kubeconfig'" in model
    assert 'application_name' in model
    assert 'def create_deployer_credential_committed(' in service
    assert 'DeployerCredentialIssueRequest' in service
    assert 'application_name' in policy


def test_deployer_access_is_service_account_only_and_namespace_scoped() -> None:
    access = (ROOT / 'app/kubernetes/tenant/access.py').read_text(encoding='utf-8')
    reconciliation = (ROOT / 'app/kubernetes/tenant/access_reconciliation.py').read_text(encoding='utf-8')
    policy = (ROOT / 'app/kubernetes/tenant/credential.py').read_text(encoding='utf-8')

    assert "return 'ServiceAccount', subject_name" in access
    assert "profile.key.value == 'deployer'" in access
    assert "subject_kind == 'ServiceAccount'" in reconciliation
    assert 'grant.scope_type != TenantAccessScope.NAMESPACE.value' in policy
    assert "grant.access_profile != 'deployer'" in policy


def test_deployer_migration_preserves_secret_material_boundary() -> None:
    migration = (ROOT / 'migrations/versions/20260926_tenant_deployer_credentials.py').read_text(encoding='utf-8')

    assert "down_revision = '20260926_tenant_credentials'" in migration
    assert 'deployer_service_account' in migration
    assert 'cicd_kubeconfig' in migration
    assert 'application_name' in migration
    assert "sa.Column('token'" not in migration
    assert "sa.Column('kubeconfig'" not in migration


def test_cicd_access_package_and_material_remain_non_secret_by_default() -> None:
    policy = (ROOT / 'app/kubernetes/tenant/credential.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/credential_service.py').read_text(encoding='utf-8')
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-credential-governance.md').read_text(encoding='utf-8')

    assert "'cicd_kubeconfig'" in policy
    assert 'create_namespaced_service_account_token' in service
    assert 'GeneratedKubeconfigMaterial' in service
    assert 'secret_material_persisted' in service
    assert 'CI/CD Namespace Access Package' in docs
    assert 'GitHub Actions' in docs
    assert 'Helm' in docs

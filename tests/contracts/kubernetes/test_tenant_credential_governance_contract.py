from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_credential_persistence_separates_metadata_from_secret_material() -> None:
    model = (ROOT / 'app/models/tenant.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260926_tenant_credentials.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/credential_service.py').read_text(encoding='utf-8')

    for token in (
        'class TenantCredential(db.Model):',
        'class TenantCredentialGeneration(db.Model):',
        "HUMAN_SERVICE_ACCOUNT = 'human_service_account'",
        "ADMIN_KUBECONFIG = 'admin_kubeconfig'",
        "SUSPENDED = 'suspended'",
        "EXPIRED = 'expired'",
        "REVOKED = 'revoked'",
    ):
        assert token in model

    assert "down_revision = '20260926_tenant_access'" in migration
    assert "sa.Column('token'" not in migration
    assert "sa.Column('kubeconfig'" not in migration
    assert 'secret_material_persisted' in service
    assert 'token: str = field(repr=False)' in service
    assert 'kubeconfig: str = field(repr=False)' in service


def test_tenant_human_credential_uses_short_lived_token_request_and_jumpserver_first_contract() -> None:
    policy = (ROOT / 'app/kubernetes/tenant/credential.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/credential_service.py').read_text(encoding='utf-8')
    reconciliation = (ROOT / 'app/kubernetes/tenant/credential_reconciliation.py').read_text(encoding='utf-8')

    assert 'DEFAULT_CREDENTIAL_VALIDITY_DAYS = 365' in policy
    assert 'DEFAULT_TOKEN_TTL_SECONDS = 3600' in policy
    assert "methods = ('jumpserver',)" in policy
    assert 'create_namespaced_service_account_token' in service
    assert 'V1TokenRequest' in service
    assert 'automount_service_account_token=False' in reconciliation
    assert "grant.access_profile == 'deployer'" in policy


def test_tenant_admin_credential_is_explicitly_separate_from_namespaced_access_grant_rbac() -> None:
    reconciliation = (ROOT / 'app/kubernetes/tenant/credential_reconciliation.py').read_text(encoding='utf-8')
    access = (ROOT / 'app/kubernetes/tenant/access_reconciliation.py').read_text(encoding='utf-8')
    policy = (ROOT / 'app/kubernetes/tenant/credential.py').read_text(encoding='utf-8')

    assert "'cluster-admin'" in reconciliation
    assert 'V1ClusterRoleBinding' in reconciliation
    assert 'ClusterRoleBinding' not in access
    assert "profile = 'cluster-admin'" in policy


def test_credential_lifecycle_removal_is_provider_enforced() -> None:
    reconciliation = (ROOT / 'app/kubernetes/tenant/credential_reconciliation.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/credential_service.py').read_text(encoding='utf-8')

    assert 'remove_native_credential_access' in reconciliation
    assert 'delete_namespaced_service_account' in reconciliation
    assert 'delete_namespaced_role_binding' in reconciliation
    assert 'delete_cluster_role_binding' in reconciliation
    assert "action='tenant_credential.revoked'" in service
    assert "action='tenant_credential.suspended'" in service
    assert "action='tenant_credential.renewed'" in service


def test_access_grant_revocation_cascades_to_dependent_human_credentials() -> None:
    access_service = (ROOT / 'app/kubernetes/tenant/access_service.py').read_text(encoding='utf-8')
    credential_service = (ROOT / 'app/kubernetes/tenant/credential_service.py').read_text(encoding='utf-8')

    assert 'revoke_credentials_for_access_grant(grant, actor=actor)' in access_service
    assert 'def revoke_credentials_for_access_grant(' in credential_service
    assert "action='tenant_credential.access_grant_revoked'" in credential_service
    assert 'reconcile_native_credential(credential)' in credential_service

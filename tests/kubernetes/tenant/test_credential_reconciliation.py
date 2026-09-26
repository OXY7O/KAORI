from types import SimpleNamespace

from kubernetes.client.rest import ApiException

from app.kubernetes.tenant import credential_reconciliation


class FakeCoreApi:
    def __init__(self) -> None:
        self.service_accounts = {}

    def read_namespaced_service_account(self, name, namespace):
        if (namespace, name) not in self.service_accounts:
            raise ApiException(status=404)
        return self.service_accounts[(namespace, name)]

    def create_namespaced_service_account(self, namespace, body):
        self.service_accounts[(namespace, body.metadata.name)] = body

    def patch_namespaced_service_account(self, name, namespace, body):
        self.service_accounts[(namespace, name)] = body

    def delete_namespaced_service_account(self, name, namespace):
        self.service_accounts.pop((namespace, name), None)


class FakeRbacApi:
    def __init__(self) -> None:
        self.roles = {}
        self.bindings = {}
        self.cluster_bindings = {}

    def read_namespaced_role(self, name, namespace):
        if (namespace, name) not in self.roles:
            raise ApiException(status=404)
        return self.roles[(namespace, name)]

    def read_namespaced_role_binding(self, name, namespace):
        if (namespace, name) not in self.bindings:
            raise ApiException(status=404)
        return self.bindings[(namespace, name)]

    def create_namespaced_role_binding(self, namespace, body):
        self.bindings[(namespace, body.metadata.name)] = body

    def patch_namespaced_role_binding(self, name, namespace, body):
        self.bindings[(namespace, name)] = body

    def delete_namespaced_role_binding(self, name, namespace):
        self.bindings.pop((namespace, name), None)

    def read_cluster_role_binding(self, name):
        if name not in self.cluster_bindings:
            raise ApiException(status=404)
        return self.cluster_bindings[name]

    def create_cluster_role_binding(self, body):
        self.cluster_bindings[body.metadata.name] = body

    def patch_cluster_role_binding(self, name, body):
        self.cluster_bindings[name] = body

    def delete_cluster_role_binding(self, name):
        self.cluster_bindings.pop(name, None)


def _credential(*, credential_type='human_service_account'):
    grant = SimpleNamespace(
        public_id='grant-1',
        access_profile='operator',
        access_profile_version=1,
    )
    return SimpleNamespace(
        public_id='11111111-2222-3333-4444-555555555555',
        tenant_id='tenant-a',
        service_account_name='kaori-human-111111112222',
        credential_type=credential_type,
        access_grant=grant if credential_type == 'human_service_account' else None,
    )


def test_human_service_account_is_non_automounted_and_bound_to_existing_profile_role(monkeypatch) -> None:
    core = FakeCoreApi()
    rbac = FakeRbacApi()
    credential = _credential()
    namespace = 'payments-dev'
    role_name = 'kaori-tenant-operator-v1'
    rbac.roles[(namespace, role_name)] = SimpleNamespace(metadata=SimpleNamespace(labels={}))

    monkeypatch.setattr(
        credential_reconciliation,
        'desired_native_access_contract',
        lambda grant, ns: {'role': {'name': role_name}},
    )

    account = credential_reconciliation._upsert_service_account(core, credential, namespace)
    binding = credential_reconciliation._upsert_human_binding(rbac, credential, namespace)

    assert account.automount_service_account_token is False
    assert binding.role_ref.kind == 'Role'
    assert binding.role_ref.name == role_name
    assert binding.subjects[0].kind == 'ServiceAccount'
    assert binding.subjects[0].namespace == namespace


def test_human_revoke_removes_binding_and_service_account(monkeypatch) -> None:
    core = FakeCoreApi()
    rbac = FakeRbacApi()
    credential = _credential()
    namespace = 'payments-dev'
    role_name = 'kaori-tenant-operator-v1'
    rbac.roles[(namespace, role_name)] = SimpleNamespace(metadata=SimpleNamespace(labels={}))

    monkeypatch.setattr(
        credential_reconciliation,
        'desired_native_access_contract',
        lambda grant, ns: {'role': {'name': role_name}},
    )
    credential_reconciliation._upsert_service_account(core, credential, namespace)
    credential_reconciliation._upsert_human_binding(rbac, credential, namespace)

    credential_reconciliation._delete_human_binding(rbac, credential, namespace)
    credential_reconciliation._delete_service_account(core, credential, namespace)

    assert core.service_accounts == {}
    assert rbac.bindings == {}


def test_admin_credential_uses_individually_owned_cluster_admin_binding() -> None:
    core = FakeCoreApi()
    rbac = FakeRbacApi()
    credential = _credential(credential_type='admin_kubeconfig')
    credential.service_account_name = 'kaori-admin-111111112222'
    namespace = 'platform-admin-anchor'

    credential_reconciliation._upsert_service_account(core, credential, namespace)
    binding = credential_reconciliation._upsert_admin_binding(rbac, credential, namespace)

    assert binding.role_ref.kind == 'ClusterRole'
    assert binding.role_ref.name == 'cluster-admin'
    assert binding.subjects[0].kind == 'ServiceAccount'
    assert binding.subjects[0].name == credential.service_account_name
    assert binding.subjects[0].namespace == namespace


def test_foreign_service_account_ownership_is_never_overwritten() -> None:
    core = FakeCoreApi()
    credential = _credential()
    namespace = 'payments-dev'
    foreign = credential_reconciliation._upsert_service_account(core, credential, namespace)
    foreign.metadata.labels['app.kubernetes.io/managed-by'] = 'other-controller'

    try:
        credential_reconciliation._upsert_service_account(core, credential, namespace)
    except ValueError as exc:
        assert 'refusing to overwrite' in str(exc)
    else:
        raise AssertionError('Foreign ServiceAccount ownership must fail closed.')

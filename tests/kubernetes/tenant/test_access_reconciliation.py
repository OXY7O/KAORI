from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from app.kubernetes.tenant import access_reconciliation
from app.kubernetes.tenant.access_reconciliation import desired_native_access_contract


class FakeRbacApi:
    def __init__(self) -> None:
        self.roles = {}
        self.bindings = {}

    def read_namespaced_role(self, name, namespace):
        if (namespace, name) not in self.roles:
            raise ApiException(status=404)
        return self.roles[(namespace, name)]

    def create_namespaced_role(self, namespace, body):
        self.roles[(namespace, body.metadata.name)] = body

    def patch_namespaced_role(self, name, namespace, body):
        self.roles[(namespace, name)] = body

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


def _grant(public_id='11111111-2222-3333-4444-555555555555'):
    membership = SimpleNamespace(
        status='active',
        principal_type='user',
        subject_name='alice',
        user=SimpleNamespace(is_active=True),
        group=None,
        tenant_id='tenant-a',
    )
    return SimpleNamespace(
        public_id=public_id,
        tenant_id='tenant-a',
        access_profile='operator',
        access_profile_version=1,
        membership=membership,
    )


def test_native_role_and_rolebinding_are_idempotent() -> None:
    api = FakeRbacApi()
    desired = desired_native_access_contract(_grant(), 'payments-dev')

    access_reconciliation._upsert_role(api, desired)
    access_reconciliation._upsert_binding(api, desired)
    access_reconciliation._upsert_role(api, desired)
    access_reconciliation._upsert_binding(api, desired)

    effective = access_reconciliation._effective_target_contract(api, desired)
    assert effective == access_reconciliation._normalized_desired(desired)


def test_shared_profile_role_remains_stable_across_multiple_grants() -> None:
    api = FakeRbacApi()
    first = _grant('11111111-2222-3333-4444-555555555555')
    second = _grant('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
    first_desired = desired_native_access_contract(first, 'payments-dev')
    second_desired = desired_native_access_contract(second, 'payments-dev')

    access_reconciliation._upsert_role(api, first_desired)
    access_reconciliation._upsert_binding(api, first_desired)
    access_reconciliation._upsert_role(api, second_desired)
    access_reconciliation._upsert_binding(api, second_desired)

    role = next(iter(api.roles.values()))
    assert 'kaori.io/access-grant' not in (role.metadata.labels or {})
    assert first_desired['role'] == second_desired['role']
    assert first_desired['role_binding']['labels']['kaori.io/access-grant'] == first.public_id
    assert second_desired['role_binding']['labels']['kaori.io/access-grant'] == second.public_id
    assert access_reconciliation._effective_target_contract(api, first_desired) == (
        access_reconciliation._normalized_desired(first_desired)
    )


def test_native_reconciliation_refuses_foreign_rolebinding_ownership() -> None:
    api = FakeRbacApi()
    desired = desired_native_access_contract(_grant(), 'payments-dev')
    binding = access_reconciliation._binding_body(desired)
    binding.metadata.labels['app.kubernetes.io/managed-by'] = 'other-controller'
    api.bindings[('payments-dev', binding.metadata.name)] = binding

    with pytest.raises(ValueError, match='refusing to overwrite'):
        access_reconciliation._upsert_binding(api, desired)


def test_revocation_removes_rolebinding_without_deleting_shared_role() -> None:
    api = FakeRbacApi()
    grant = _grant()
    desired = desired_native_access_contract(grant, 'payments-dev')
    access_reconciliation._upsert_role(api, desired)
    access_reconciliation._upsert_binding(api, desired)

    access_reconciliation._delete_binding(api, grant, 'payments-dev')

    assert api.bindings == {}
    assert len(api.roles) == 1


def test_effective_contract_detects_rolebinding_drift() -> None:
    api = FakeRbacApi()
    desired = desired_native_access_contract(_grant(), 'payments-dev')
    access_reconciliation._upsert_role(api, desired)
    access_reconciliation._upsert_binding(api, desired)

    binding = next(iter(api.bindings.values()))
    binding.role_ref.name = 'unexpected-role'

    assert access_reconciliation._effective_target_contract(api, desired) != (
        access_reconciliation._normalized_desired(desired)
    )

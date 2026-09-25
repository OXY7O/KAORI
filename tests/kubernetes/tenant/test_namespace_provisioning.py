from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from app.kubernetes.tenant import provisioning


class FakeCoreApi:
    def __init__(self) -> None:
        self.namespaces = {}
        self.quotas = {}
        self.limits = {}

    def read_namespace(self, name):
        if name not in self.namespaces:
            raise ApiException(status=404)
        return self.namespaces[name]

    def create_namespace(self, body):
        self.namespaces[body.metadata.name] = body

    def patch_namespace(self, name, body):
        self.namespaces[name] = body

    def read_namespaced_resource_quota(self, name, namespace):
        if (namespace, name) not in self.quotas:
            raise ApiException(status=404)
        return self.quotas[(namespace, name)]

    def create_namespaced_resource_quota(self, namespace, body):
        self.quotas[(namespace, body.metadata.name)] = body

    def patch_namespaced_resource_quota(self, name, namespace, body):
        self.quotas[(namespace, name)] = body

    def read_namespaced_limit_range(self, name, namespace):
        if (namespace, name) not in self.limits:
            raise ApiException(status=404)
        return self.limits[(namespace, name)]

    def create_namespaced_limit_range(self, namespace, body):
        self.limits[(namespace, body.metadata.name)] = body

    def patch_namespaced_limit_range(self, name, namespace, body):
        self.limits[(namespace, name)] = body


def _desired():
    return {
        'namespace': 'payments-dev',
        'labels': {
            'app.kubernetes.io/managed-by': 'kaori',
            'kaori.io/tenant-id': 'tenant-1',
            'kaori.io/environment': 'development',
            'kaori.io/resource-profile': 'profile-1',
        },
        'quota': {'requests.cpu': '2', 'pods': '20'},
        'limits': {
            'default': {'cpu': '500m'},
            'default_request': {'cpu': '100m'},
        },
        'provider_key': 'native_kubernetes',
    }


def test_native_namespace_resources_are_idempotent() -> None:
    api = FakeCoreApi()
    desired = _desired()

    provisioning._upsert_namespace(api, desired)
    provisioning._upsert_quota(api, desired)
    provisioning._upsert_limit_range(api, desired)
    provisioning._upsert_namespace(api, desired)
    provisioning._upsert_quota(api, desired)
    provisioning._upsert_limit_range(api, desired)

    effective = provisioning._effective_contract(api, desired)
    assert effective == desired


def test_reconciliation_refuses_foreign_resource_ownership() -> None:
    api = FakeCoreApi()
    desired = _desired()
    api.namespaces['payments-dev'] = SimpleNamespace(
        metadata=SimpleNamespace(labels={'app.kubernetes.io/managed-by': 'other-controller'})
    )

    with pytest.raises(ValueError, match='refusing to overwrite'):
        provisioning._upsert_namespace(api, desired)

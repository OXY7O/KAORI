from types import SimpleNamespace

from kubernetes.client.rest import ApiException

from app.kubernetes.tenant.allocation_observation import (
    observe_capsule_tenant_allocation,
    observe_native_namespace_allocation,
    profile_lineage_for_observed_allocation,
)


def _metadata(name, *, uid=None, resource_version='1', labels=None, owner_references=None):
    return SimpleNamespace(
        name=name,
        uid=uid or f'uid-{name}',
        resource_version=resource_version,
        labels=labels or {},
        owner_references=owner_references or [],
    )


def _quota(name, hard):
    return SimpleNamespace(
        metadata=_metadata(name),
        spec=SimpleNamespace(hard=hard),
    )


def _limit_range(name, *, default=None, default_request=None):
    item = SimpleNamespace(
        type='Container',
        default=default or {},
        default_request=default_request or {},
    )
    return SimpleNamespace(
        metadata=_metadata(name),
        spec=SimpleNamespace(limits=[item]),
    )


class FakeCoreApi:
    def __init__(self, *, namespaces=None, quotas=None, limit_ranges=None):
        self._namespaces = namespaces or []
        self._quotas = quotas or {}
        self._limit_ranges = limit_ranges or {}

    def list_namespace(self, **_kwargs):
        return SimpleNamespace(items=self._namespaces)

    def list_namespaced_resource_quota(self, namespace, **_kwargs):
        return SimpleNamespace(items=self._quotas.get(namespace, []))

    def list_namespaced_limit_range(self, namespace, **_kwargs):
        return SimpleNamespace(items=self._limit_ranges.get(namespace, []))


class EmptyCapsuleCustomApi:
    def list_cluster_custom_object(self, *_args, **_kwargs):
        raise ApiException(status=404)


class FakeClient:
    def __init__(self, core_api):
        self._core_api = core_api
        self._custom_api = EmptyCapsuleCustomApi()

    def core_api(self):
        return self._core_api

    def custom_objects_api(self):
        return self._custom_api


def test_native_observation_captures_custom_legacy_allocation_without_mutation():
    api = FakeCoreApi(
        quotas={
            'api-prod': [
                _quota(
                    'legacy-quota',
                    {
                        'limits.cpu': '4',
                        'limits.memory': '8Gi',
                        'pods': '10',
                        'requests.storage': '1Gi',
                    },
                )
            ]
        },
        limit_ranges={
            'api-prod': [
                _limit_range(
                    'legacy-limits',
                    default={'cpu': '500m', 'memory': '512Mi'},
                    default_request={'cpu': '100m', 'memory': '128Mi'},
                )
            ]
        },
    )

    observed = observe_native_namespace_allocation(api, 'api-prod')

    assert observed['provenance'] == 'adopted_observed'
    assert observed['control_state'] == 'observed'
    assert observed['quota']['limits.cpu'] == '4'
    assert observed['quota']['limits.memory'] == '8Gi'
    assert observed['quota']['pods'] == '10'
    assert observed['quota']['requests.storage'] == '1Gi'
    assert observed['limits']['default']['cpu'] == '500m'
    assert observed['profile_lineage']['kind'] == 'custom_observed_baseline'
    assert observed['provider_mutation_performed'] is False
    assert observed['effective_hash']


def test_native_observation_fails_closed_when_multiple_quotas_own_same_dimension():
    api = FakeCoreApi(
        quotas={
            'api-prod': [
                _quota('quota-a', {'pods': '10'}),
                _quota('quota-b', {'pods': '20'}),
            ]
        }
    )

    observed = observe_native_namespace_allocation(api, 'api-prod')

    assert observed['control_state'] == 'control_unavailable'
    assert observed['quota'] == {}
    assert any('pods is defined by multiple quota sources' in item for item in observed['ambiguous_dimensions'])


def test_semantic_quantity_match_preserves_locked_preset_lineage():
    quota = {
        'requests.cpu': '2000m',
        'limits.cpu': '4',
        'requests.memory': '4096Mi',
        'limits.memory': '8Gi',
        'pods': '20',
        'persistentvolumeclaims': '10',
        'requests.storage': '100Gi',
        'services': '10',
        'configmaps': '50',
        'secrets': '50',
    }
    limits = {
        'default_request': {'cpu': '0.1', 'memory': '128Mi'},
        'default': {'cpu': '500m', 'memory': '512Mi'},
    }

    lineage = profile_lineage_for_observed_allocation(quota, limits)

    assert lineage == {
        'kind': 'kaori_preset',
        'profile_class': 'standard',
        'profile_version': 1,
        'label': 'Standard · KAORI Preset',
    }


def test_capsule_tenant_quota_is_preserved_but_control_remains_unavailable():
    namespace = SimpleNamespace(
        metadata=_metadata(
            'api-prod',
            labels={'capsule.clastix.io/tenant': 'api'},
        )
    )
    core = FakeCoreApi(namespaces=[namespace])
    client = FakeClient(core)
    tenant_item = {
        'metadata': {'name': 'api', 'uid': 'tenant-api', 'resourceVersion': '7'},
        'status': {'namespaces': ['api-prod']},
        'spec': {
            'resourceQuotas': {
                'scope': 'Tenant',
                'items': [{'hard': {'limits.cpu': '4', 'limits.memory': '8Gi', 'pods': '10'}}],
            }
        },
    }

    observed = observe_capsule_tenant_allocation(
        client,
        tenant_name='api',
        tenant_item=tenant_item,
    )

    assert observed['allocation_authority'] == 'capsule_tenant_resource_quotas'
    assert observed['shared_quota'] == {
        'limits.cpu': '4',
        'limits.memory': '8Gi',
        'pods': '10',
    }
    assert observed['correlated_namespaces'][0]['name'] == 'api-prod'
    assert observed['control_state'] == 'control_unavailable'
    assert 'has not admitted that mutation path' in observed['control_reason']
    assert observed['provider_mutation_performed'] is False

def test_capsule_tenant_quota_treats_matching_native_quota_as_materialization():
    namespace = SimpleNamespace(
        metadata=_metadata(
            'api-prod',
            labels={'capsule.clastix.io/tenant': 'api'},
        )
    )
    core = FakeCoreApi(
        namespaces=[namespace],
        quotas={
            'api-prod': [
                _quota(
                    'capsule-api-0',
                    {
                        'limits.cpu': '4',
                        'limits.memory': '8Gi',
                        'pods': '10',
                    },
                )
            ]
        },
    )
    client = FakeClient(core)
    tenant_item = {
        'metadata': {'name': 'api', 'uid': 'tenant-api', 'resourceVersion': '7'},
        'status': {'namespaces': ['api-prod']},
        'spec': {
            'resourceQuotas': {
                'scope': 'Tenant',
                'items': [
                    {'hard': {'limits.cpu': '4', 'limits.memory': '8Gi'}},
                    {'hard': {'pods': '10'}},
                ],
            }
        },
    }

    observed = observe_capsule_tenant_allocation(
        client,
        tenant_name='api',
        tenant_item=tenant_item,
    )

    assert observed['allocation_authority'] == 'capsule_tenant_resource_quotas'
    assert observed['authority_paths'] == ['capsule_tenant_resource_quotas']
    assert not any(
        'Multiple effective allocation authority paths' in item
        for item in observed['ambiguous_dimensions']
    )

def test_native_observation_fails_closed_on_unsupported_limit_range_constraints():
    item = SimpleNamespace(
        type='Container',
        default={'cpu': '500m'},
        default_request={'cpu': '100m'},
        max={'cpu': '2'},
        min={},
        max_limit_request_ratio={},
    )
    api = FakeCoreApi(
        limit_ranges={
            'api-prod': [
                SimpleNamespace(
                    metadata=_metadata('legacy-limits'),
                    spec=SimpleNamespace(limits=[item]),
                )
            ]
        }
    )

    observed = observe_native_namespace_allocation(api, 'api-prod')

    assert observed['control_state'] == 'control_unavailable'
    assert 'LimitRange/legacy-limits:max.cpu' in observed['unsupported_dimensions']


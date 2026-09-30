from types import SimpleNamespace

import pytest

import app.kubernetes.tenant.capsule_tenant_quota_governance as governance
from app.kubernetes.tenant.capsule_tenant_quota_governance import (
    _desired_resource_quotas,
    _patch_resource_quotas,
    _read_live_tenant,
    accept_capsule_tenant_provider_state,
    build_capsule_tenant_quota_cutover_state,
    reapply_capsule_tenant_quota_intent,
)


def _tenant(*, blockers=None, external_constraints=None, control_state=None):
    allocation_governance = {}
    if control_state is not None:
        allocation_governance = {
            'authority': 'capsule_tenant_resource_quotas',
            'capability': 'tenant_resource_quotas',
            'control_state': control_state,
            'allocation_scope': 'tenant_shared',
            'scope': 'Tenant',
            'resource_profile_id': 'profile-1',
            'resource_profile_version': 1,
            'desired_resource_quotas': {
                'scope': 'Tenant',
                'items': [
                    {
                        'hard': {
                            'requests.cpu': '4',
                            'requests.memory': '8Gi',
                        }
                    }
                ],
            },
            'effective_resource_quotas': {
                'scope': 'Tenant',
                'items': [
                    {
                        'hard': {
                            'requests.cpu': '4',
                            'requests.memory': '8Gi',
                        }
                    }
                ],
            },
            'desired_quota': {
                'requests.cpu': '4',
                'requests.memory': '8Gi',
            },
            'effective_quota': {
                'requests.cpu': '4',
                'requests.memory': '8Gi',
            },
            'provider_source': {
                'kind': 'Tenant',
                'name': 'partner',
                'uid': 'tenant-partner',
                'resource_version': '12',
                'api_version': 'v1beta2',
            },
            'provenance': 'kaori_managed',
            'history': [],
            'external_constraints': list(external_constraints or []),
            'correlated_namespace_count': 1,
        }
        if control_state == 'drifted':
            allocation_governance['allocation_drift'] = {
                'observed_hash': 'observed',
                'provider_source': {
                    'kind': 'Tenant',
                    'name': 'partner',
                    'uid': 'tenant-partner',
                    'resource_version': '13',
                    'api_version': 'v1beta2',
                },
                'blocked_reasons': [],
            }

    return SimpleNamespace(
        id='tenant-partner',
        cluster_id='cluster-1',
        name='partner',
        slug='partner',
        provider_key='capsule',
        provider_state='capsule',
        reconciliation_authority='capsule',
        lifecycle_status='ready',
        provider_reference='partner',
        provider_evidence_json={
            'provider_api_version': 'v1beta2',
            'resource_name': 'partner',
            'provider_uid': 'tenant-partner',
            'resource_version': '12',
            'capsule': {
                'capabilities': {
                    'tenant_resource_quotas': 'available',
                }
            },
            'allocation_baseline': {
                'allocation_authority': 'capsule_tenant_resource_quotas',
                'authority_unsupported_dimensions': list(blockers or []),
                'authority_ambiguous_dimensions': [],
                'external_constraints': list(external_constraints or []),
                'tenant_resource_quota': {
                    'scope': 'Tenant',
                    'quota': {
                        'requests.cpu': '4',
                        'requests.memory': '8Gi',
                    },
                    'items': [
                        {
                            'hard': {
                                'requests.cpu': '4',
                                'requests.memory': '8Gi',
                            }
                        }
                    ],
                },
                'correlated_namespaces': [{'name': 'partner-dev'}],
            },
            'allocation_governance': allocation_governance,
        },
    )


def _profile(quota=None):
    return SimpleNamespace(
        id=5,
        public_id='profile-1',
        version=1,
        profile_class='custom',
        quota_hard_json=quota
        or {
            'requests.cpu': '4',
            'requests.memory': '8Gi',
        },
        limit_defaults_json={},
        enabled=True,
    )


class _FakeCustomApi:
    def __init__(self, item):
        self.item = item
        self.patch_calls = []

    def get_cluster_custom_object(self, *_args, **_kwargs):
        return self.item

    def patch_cluster_custom_object(self, *args, **kwargs):
        self.patch_calls.append((args, kwargs))
        resource_quotas = kwargs.get('body', {}).get('spec', {}).get('resourceQuotas')
        if resource_quotas is None and len(args) >= 5 and isinstance(args[4], dict):
            resource_quotas = args[4].get('spec', {}).get('resourceQuotas')
        if resource_quotas is not None:
            self.item = {
                **self.item,
                'metadata': {
                    **self.item.get('metadata', {}),
                    'resourceVersion': '14',
                },
                'spec': {
                    **self.item.get('spec', {}),
                    'resourceQuotas': resource_quotas,
                },
            }
        return self.item


class _FakeClient:
    def __init__(self, api):
        self.api = api

    def custom_objects_api(self):
        return self.api


def test_external_namespace_constraint_does_not_block_tenant_quota_cutover() -> None:
    tenant = _tenant(
        external_constraints=[
            'Namespace/partner-dev: LimitRange/capsule-partner-0/type=PersistentVolumeClaim'
        ]
    )

    state = build_capsule_tenant_quota_cutover_state(tenant)

    assert state['supported'] is True
    assert state['state'] == 'adopted_observed'
    assert state['scope'] == 'Tenant'
    assert state['external_constraints']


def test_authoritative_unsupported_field_blocks_tenant_quota_cutover() -> None:
    tenant = _tenant(
        blockers=['Tenant.spec.resourceQuotas.items[0].scopeSelector']
    )

    state = build_capsule_tenant_quota_cutover_state(tenant)

    assert state['supported'] is False
    assert state['state'] == 'control_unavailable'
    assert 'unsupported dimensions' in state['reason']


def test_desired_resource_quotas_preserve_item_order_and_key_ownership() -> None:
    current = {
        'scope': 'Tenant',
        'items': [
            {'hard': {'limits.cpu': '8', 'pods': '20'}},
            {'hard': {'limits.memory': '8Gi'}},
        ],
    }

    desired = _desired_resource_quotas(
        current,
        {
            'limits.cpu': '4',
            'limits.memory': '4Gi',
            'pods': '10',
            'requests.storage': '1Gi',
        },
        scope='Tenant',
    )

    assert desired['scope'] == 'Tenant'
    assert desired['items'][0]['hard'] == {
        'limits.cpu': '4',
        'pods': '10',
        'requests.storage': '1Gi',
    }
    assert desired['items'][1]['hard'] == {'limits.memory': '4Gi'}


def test_stale_resource_version_blocks_before_provider_patch(monkeypatch) -> None:
    tenant = _tenant()
    item = {
        'metadata': {
            'name': 'partner',
            'uid': 'tenant-partner',
            'resourceVersion': '13',
        },
        'spec': {
            'resourceQuotas': {
                'scope': 'Tenant',
                'items': [{'hard': {'requests.cpu': '4', 'requests.memory': '8Gi'}}],
            }
        },
    }
    api = _FakeCustomApi(item)
    client = _FakeClient(api)
    monkeypatch.setattr(
        governance,
        '_cluster_client',
        lambda _tenant: (SimpleNamespace(id='cluster-1'), client),
    )

    with pytest.raises(ValueError, match='resourceVersion changed'):
        _read_live_tenant(
            tenant,
            expected_source={
                'name': 'partner',
                'uid': 'tenant-partner',
                'resource_version': '12',
                'api_version': 'v1beta2',
            },
            require_resource_version_match=True,
        )

    assert api.patch_calls == []


def test_provider_patch_changes_only_tenant_resource_quotas() -> None:
    tenant = _tenant()
    item = {
        'metadata': {
            'name': 'partner',
            'uid': 'tenant-partner',
            'resourceVersion': '12',
            'labels': {'keep': 'me'},
        },
        'spec': {
            'owners': [{'kind': 'User', 'name': 'APE'}],
            'resourceQuotas': {
                'scope': 'Tenant',
                'items': [{'hard': {'requests.cpu': '2', 'requests.memory': '4Gi'}}],
            },
        },
    }
    api = _FakeCustomApi(item)
    client = _FakeClient(api)
    desired = {
        'scope': 'Tenant',
        'items': [{'hard': {'requests.cpu': '4', 'requests.memory': '8Gi'}}],
    }

    _verified, source, observed = _patch_resource_quotas(
        tenant,
        current_source={
            'kind': 'Tenant',
            'name': 'partner',
            'uid': 'tenant-partner',
            'resource_version': '12',
            'api_version': 'v1beta2',
        },
        desired_resource_quotas=desired,
        client=client,
    )

    assert len(api.patch_calls) == 1
    args, kwargs = api.patch_calls[0]
    body = kwargs.get('body') or args[4]
    assert set(body) == {'metadata', 'spec'}
    assert set(body['spec']) == {'resourceQuotas'}
    assert body['metadata']['resourceVersion'] == '12'
    assert source['resource_version'] == '14'
    assert observed['quota']['requests.cpu'] == '4'


def test_accept_provider_state_commits_live_quota_without_provider_write(monkeypatch) -> None:
    tenant = _tenant(control_state='drifted')
    profile = _profile()
    live_quota = {
        'scope': 'Tenant',
        'quota': {
            'requests.cpu': '6',
            'requests.memory': '10Gi',
        },
        'items': [
            {
                'hard': {
                    'requests.cpu': '6',
                    'requests.memory': '10Gi',
                }
            }
        ],
        'unsupported_dimensions': [],
        'ambiguous_dimensions': [],
    }
    source = {
        'kind': 'Tenant',
        'name': 'partner',
        'uid': 'tenant-partner',
        'resource_version': '13',
        'api_version': 'v1beta2',
    }
    monkeypatch.setattr(
        governance,
        '_fresh_drift_observation',
        lambda _tenant: (
            {},
            source,
            object(),
            live_quota,
            {
                'external_constraints': [
                    'Namespace/partner-dev: LimitRange/capsule-partner-0/type=PersistentVolumeClaim'
                ],
                'correlated_namespaces': [{'name': 'partner-dev'}],
            },
        ),
    )
    monkeypatch.setattr(governance, '_lineage_profile', lambda _tenant: profile)
    monkeypatch.setattr(
        governance,
        'enforce_capsule_tenant_resource_quota_preflight',
        lambda **_kwargs: SimpleNamespace(id=77),
    )

    def forbidden_patch(*_args, **_kwargs):
        raise AssertionError('Accept Provider State must not write provider state.')

    monkeypatch.setattr(governance, '_patch_resource_quotas', forbidden_patch)

    accept_capsule_tenant_provider_state(tenant)

    committed = tenant.provider_evidence_json['allocation_governance']
    assert committed['control_state'] == 'kaori_managed'
    assert committed['desired_quota'] == {
        'requests.cpu': '6',
        'requests.memory': '10Gi',
    }
    assert committed['provider_mutation_performed'] is False
    assert committed['provenance'] == 'accepted_provider_state'
    assert committed['external_constraints']


def test_reapply_uses_fresh_live_provider_allocation_for_capacity(monkeypatch) -> None:
    tenant = _tenant(control_state='drifted')
    profile = _profile()
    live_quota = {
        'scope': 'Tenant',
        'quota': {
            'requests.cpu': '2',
            'requests.memory': '4Gi',
        },
        'items': [
            {
                'hard': {
                    'requests.cpu': '2',
                    'requests.memory': '4Gi',
                }
            }
        ],
        'unsupported_dimensions': [],
        'ambiguous_dimensions': [],
    }
    source = {
        'kind': 'Tenant',
        'name': 'partner',
        'uid': 'tenant-partner',
        'resource_version': '13',
        'api_version': 'v1beta2',
    }
    allocation = {
        'external_constraints': [],
        'correlated_namespaces': [{'name': 'partner-dev'}],
    }
    monkeypatch.setattr(
        governance,
        '_fresh_drift_observation',
        lambda _tenant: ({}, source, object(), live_quota, allocation),
    )
    monkeypatch.setattr(governance, '_lineage_profile', lambda _tenant: profile)
    captured = {}

    def capacity(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=88)

    monkeypatch.setattr(
        governance,
        'enforce_capsule_tenant_resource_quota_preflight',
        capacity,
    )
    desired = tenant.provider_evidence_json['allocation_governance']['desired_resource_quotas']
    verified = {
        'scope': 'Tenant',
        'quota': {
            'requests.cpu': '4',
            'requests.memory': '8Gi',
        },
        'items': desired['items'],
        'unsupported_dimensions': [],
        'ambiguous_dimensions': [],
    }
    monkeypatch.setattr(
        governance,
        '_patch_resource_quotas',
        lambda *_args, **_kwargs: ({}, {**source, 'resource_version': '14'}, verified),
    )

    reapply_capsule_tenant_quota_intent(tenant)

    assert captured['current_quota_hard'] == {
        'requests.cpu': '2',
        'requests.memory': '4Gi',
    }
    assert captured['proposed_quota_hard'] == {
        'requests.cpu': '4',
        'requests.memory': '8Gi',
    }
    assert tenant.provider_evidence_json['allocation_governance']['control_state'] == 'kaori_managed'
    assert tenant.provider_evidence_json['allocation_governance']['provider_mutation_performed'] is True

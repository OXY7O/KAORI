"""#1229 Capsule related ResourceQuota/LimitRange/RoleBinding inventory regression fixtures.

Authored only; no pytest or CI execution in DevContainer review HOLD.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    classify_capsule_related_resource,
    observe_capsule_related_inventory,
)


def _resource(kind='ResourceQuota', *, name='control', manager='capsule',
              labels=None, owner_refs=None, uid='obj-uid', rv='9', spec=None):
    observed_labels = (
        labels if labels is not None else {
            'app.kubernetes.io/managed-by': manager,
            'capsule.clastix.io/tenant': 'demo',
            'foreign.example/retain': 'true',
        }
    )
    obj = SimpleNamespace(
        metadata=SimpleNamespace(
            name=name, uid=uid, resource_version=rv, namespace='demo-dev',
            labels=observed_labels, annotations={'foreign.example/note': 'unchanged'},
            owner_references=owner_refs if owner_refs is not None else [
                {'kind': 'Tenant', 'apiVersion': 'capsule.clastix.io/v1beta2',
                 'name': 'demo', 'uid': 'cr-uid'}
            ],
            finalizers=['capsule.clastix.io/preserve'],
        ),
    )
    if kind == 'RoleBinding':
        obj.role_ref = {'kind': 'ClusterRole', 'name': 'view', 'apiGroup': 'rbac.authorization.k8s.io'}
        obj.subjects = [{'kind': 'User', 'name': 'external-user'}]
    else:
        obj.spec = spec if spec is not None else (
            {'hard': {'requests.cpu': '1'}} if kind == 'ResourceQuota'
            else {'limits': [{'type': 'Container', 'max': {'memory': '1Gi'}}]}
        )
    return obj


def _classify(item, *, kind='ResourceQuota'):
    return classify_capsule_related_resource(
        resource=item, kind=kind, namespace='demo-dev',
        tenant_id='tenant-uuid', capsule_name='demo', capsule_uid='cr-uid',
    )


class _API:
    def __init__(self, **objects):
        self.objects = objects
        self.calls = []

    def _list(self, kind, namespace, **kwargs):
        self.calls.append((kind, namespace, kwargs))
        return SimpleNamespace(
            metadata=SimpleNamespace(resource_version='list-rv', _continue=''),
            items=deepcopy(self.objects.get(kind, [])),
        )

    def list_namespaced_resource_quota(self, namespace, **kwargs):
        return self._list('ResourceQuota', namespace, **kwargs)

    def list_namespaced_limit_range(self, namespace, **kwargs):
        return self._list('LimitRange', namespace, **kwargs)

    def list_namespaced_role_binding(self, namespace, **kwargs):
        return self._list('RoleBinding', namespace, **kwargs)


def _scope():
    return [{
        'kind': 'Namespace', 'authority': 'capsule',
        'namespace': 'demo-dev', 'name': 'demo-dev',
        'uid': 'ns-uid', 'resource_version': '7',
    }]


def _observe(core, rbac, scope=None):
    return observe_capsule_related_inventory(
        core=core, rbac=rbac, namespace_components=scope if scope is not None else _scope(),
        tenant_id='tenant-uuid', capsule_name='demo', capsule_uid='cr-uid',
    )


def test_provider_owned_and_external_policy_are_observed_not_claimed():
    items = [
        _resource(),
        _resource('LimitRange', name='external', labels={
            'app.kubernetes.io/managed-by': 'other-operator',
            'foreign.example/retain': 'yes',
        }, owner_refs=[]),
    ]
    first, problems = _classify(items[0])
    assert first['origin'] == 'capsule_provider' and problems == []
    second, problems = _classify(items[1], kind='LimitRange')
    assert second['origin'] == 'foreign_preserved' and problems == []
    assert second['mutation_authorized'] == 'false'


def test_kaori_owned_allocation_or_access_is_visible_and_blocks_provider_handoff():
    quota = _resource(labels={
        'app.kubernetes.io/managed-by': 'kaori',
        'kaori.io/tenant-id': 'tenant-uuid',
        'capsule.clastix.io/tenant': 'demo',
    })
    grant = _resource('RoleBinding', labels={
        'app.kubernetes.io/managed-by': 'kaori',
        'kaori.io/tenant-id': 'tenant-uuid',
        'kaori.io/access-grant': 'grant-id',
        'capsule.clastix.io/tenant': 'demo',
    })
    for kind, item in [('ResourceQuota', quota), ('RoleBinding', grant)]:
        evidence, blockers = _classify(item, kind=kind)
        assert evidence['origin'] == 'kaori_correlated'
        assert len(blockers) == 1
        assert 'handoff' in blockers[0] or 'controls' in blockers[0]


@pytest.mark.parametrize('changes', [
    {'app.kubernetes.io/managed-by': 'kaori', 'kaori.io/tenant-id': 'other'},
    {'app.kubernetes.io/managed-by': 'capsule', 'kaori.io/tenant-id': 'tenant-uuid'},
    {'app.kubernetes.io/managed-by': 'kaori', 'kaori.io/tenant-id': 'tenant-uuid',
     'kaori.io/unknown': 'value'},
    {},
])
def test_ambiguous_unattributed_or_spoofed_kaori_origin_never_admitted(changes):
    item = _resource(labels=changes, owner_refs=[])
    evidence, blockers = _classify(item)
    assert blockers
    assert evidence['origin'] in ('ambiguous_kaori', 'unattributed')


@pytest.mark.parametrize('owner', [
    [{'kind': 'Tenant', 'apiVersion': 'capsule.clastix.io/v1beta2',
      'name': 'another', 'uid': 'cr-uid'}],
    [{'kind': 'Tenant', 'apiVersion': 'capsule.clastix.io/v1beta2',
      'name': 'demo', 'uid': 'foreign-uid'}],
    [{'kind': 'Controller', 'apiVersion': 'foreign.example/v1',
      'name': 'operator', 'uid': 'third-party'}],
])
def test_foreign_or_recreated_cr_owner_reference_blocks(owner):
    evidence, blockers = _classify(_resource(owner_refs=owner))
    assert blockers
    assert evidence['mutation_authorized'] == 'false'


def test_policy_rv_and_foreign_metadata_changes_affect_digest_not_plaintext():
    item = _resource()
    first, _ = _classify(item)
    item.spec['hard']['requests.cpu'] = '9'
    after, _ = _classify(item)
    assert first['policy_sha256'] != after['policy_sha256']
    assert 'requests.cpu' not in str(first)
    item.metadata.annotations['foreign.example/note'] = 'modified'
    third, _ = _classify(item)
    assert after['metadata_sha256'] != third['metadata_sha256']
    assert item.metadata.annotations['foreign.example/note'] not in str(third)
    item.metadata.resource_version = '10'
    assert _classify(item)[0]['resource_version'] != first['resource_version']


def test_complete_three_kind_inventory_is_bounded_and_read_only():
    core = _API(ResourceQuota=[_resource()], LimitRange=[_resource('LimitRange')])
    rbac = _API(RoleBinding=[_resource('RoleBinding')])
    result = _observe(core, rbac)
    assert result['resource_count'] == 3
    assert result['status'] == 'read_only_related_inventory'
    assert not result['blockers']
    assert len(result['resource_sha256']) == 64
    assert result['provider_mutation_performed'] is False
    assert result['provider_handoff_verified'] is False
    assert result['shared_quota_and_controller_origin_verified'] is False
    assert len(core.calls) == 2 and len(rbac.calls) == 1
    for _, namespace, kwargs in core.calls + rbac.calls:
        assert namespace == 'demo-dev'
        assert kwargs == {'limit': 101, '_request_timeout': 5}


def test_added_deleted_or_reordered_provider_objects_change_fingerprint():
    item = _resource()
    first = _observe(_API(ResourceQuota=[item]), _API())
    second = _observe(_API(ResourceQuota=[item, _resource(name='extra', uid='extra-uid')]), _API())
    assert first['resource_sha256'] != second['resource_sha256']
    reordered = _observe(_API(ResourceQuota=list(reversed([
        item, _resource(name='extra', uid='extra-uid'),
    ]))), _API())
    assert second['resource_sha256'] == reordered['resource_sha256']


@pytest.mark.parametrize('bad', [
    [],
    [{'kind': 'Namespace', 'name': 'demo-dev', 'namespace': 'different',
      'uid': 'ns-uid', 'resource_version': '7'}],
    _scope() + _scope(),
])
def test_incomplete_or_duplicated_namespace_scope_is_rejected(bad):
    with pytest.raises(ValueError):
        _observe(_API(), _API(), scope=bad)


def test_malformed_provider_policy_and_list_fail_closed():
    incomplete = _resource(spec={'hard': {'cpu': float('nan')}})
    with pytest.raises(ValueError):
        _observe(_API(ResourceQuota=[incomplete]), _API())
    oversized = _API(ResourceQuota=[_resource(name=str(i), uid=str(i)) for i in range(101)])
    with pytest.raises(ValueError):
        _observe(oversized, _API())
    missing_list_rv = _API()
    missing_list_rv._list = lambda *args, **kwargs: SimpleNamespace(
        metadata=SimpleNamespace(resource_version=None), items=[],
    )
    with pytest.raises(ValueError):
        _observe(missing_list_rv, _API())
    partial = _API()
    partial._list = lambda *args, **kwargs: SimpleNamespace(
        metadata=SimpleNamespace(resource_version='list-rv', _continue='page-2'), items=[],
    )
    with pytest.raises(ValueError):
        _observe(partial, _API())


def test_preflight_keeps_native_shape_and_binds_capsule_sha_to_current_fingerprint():
    from pathlib import Path

    preflight = Path('app/kubernetes/tenant/release_preflight.py').read_text()
    assert "capsule_cr['capsule_related_resources_sha256']" in preflight
    assert "capsule_cr['capsule_related_resources_count']" in preflight
    assert "evidence['capsule_related_inventory'] = capsule_related_inventory" in preflight
    assert 'if tenant.provider_key == \'capsule\':' in preflight
    assert 'observe_capsule_related_inventory(' in preflight
    assert 'resource_sha256' in preflight


def test_changed_provider_list_revision_invalidates_related_scope_digest():
    first = _observe(_API(), _API())
    core = _API()
    original_list = core._list

    def changed_list(kind, namespace, **kwargs):
        payload = original_list(kind, namespace, **kwargs)
        payload.metadata.resource_version = 'new-list-rv'
        return payload

    core._list = changed_list
    changed = _observe(core, _API())
    assert first['resource_count'] == changed['resource_count'] == 0
    assert first['resource_sha256'] != changed['resource_sha256']
    assert changed['list_snapshots'][0]['list_resource_version'] == 'new-list-rv'


@pytest.mark.parametrize('conflict', ['foreign_owner', 'wrong_capsule_tenant', 'wrong_capsule_uid'])
def test_kaori_labels_cannot_override_foreign_or_conflicting_capsule_origin(conflict):
    labels = {
        'app.kubernetes.io/managed-by': 'kaori',
        'kaori.io/tenant-id': 'tenant-uuid',
        'capsule.clastix.io/tenant': 'demo',
    }
    owners = [
        {'kind': 'Tenant', 'apiVersion': 'capsule.clastix.io/v1beta2',
         'name': 'demo', 'uid': 'cr-uid'},
    ]
    if conflict == 'foreign_owner':
        owners.append({
            'kind': 'ConfigMap', 'apiVersion': 'v1',
            'name': 'foreign-controller', 'uid': 'foreign-uid',
        })
    elif conflict == 'wrong_capsule_tenant':
        labels['capsule.clastix.io/tenant'] = 'another-tenant'
    else:
        owners[0]['uid'] = 'foreign-capsule-uid'
    for kind in ('ResourceQuota', 'LimitRange', 'RoleBinding'):
        source = _resource(kind, labels={
            **labels,
            **({'kaori.io/access-grant': 'grant-id'} if kind == 'RoleBinding' else {}),
        }, owner_refs=owners)
        evidence, problems = _classify(source, kind=kind)
        assert evidence['origin'] == 'ambiguous_kaori'
        assert evidence['mutation_authorized'] == 'false'
        assert problems

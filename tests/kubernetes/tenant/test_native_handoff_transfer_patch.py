"""Pure #1048 patch-contract checks; no Kubernetes provider writes."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.native_handoff_transfer_patch import (
    build_native_successor_handoff_patch,
)


def _resource():
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='tenant-dev', uid='uid-11', resource_version='27',
            labels={
                'app.kubernetes.io/managed-by': 'kaori',
                'kaori.io/tenant-id': 'tenant-1',
                'kaori.io/environment': 'development',
                'kaori.io/resource-profile': 'profile-v4',
                'kaori.io/tenant-generation': '4',
                'kaori.io/profile-id': 'profile-4',
                'example.com/external': 'preserved',
            },
            annotations={'example.com/audit': 'keep'},
            owner_references=[], finalizers=['keep'], generation=1,
        ),
        spec={'hard': {'limits.cpu': '8', 'limits.memory': '16Gi'}},
    )


def _component(kind='Namespace'):
    return {
        'kind': kind, 'name': 'tenant-dev',
        'namespace': 'tenant-dev', 'uid': 'uid-11', 'resource_version': '27',
        'handoff': 'external_acceptance_required',
        'ownership': 'kaori_marker_correlated',
    }


@pytest.mark.parametrize('kind', ['Namespace', 'ResourceQuota', 'LimitRange'])
def test_successor_patch_is_only_cas_owner_transfer_metadata(kind):
    resource = _resource()
    before = deepcopy(resource)
    ops = build_native_successor_handoff_patch(
        _component(kind), resource, tenant_id='tenant-1',
        verified_successor_owner='platform-team',
    )
    assert ops[:4] == [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'uid-11'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '27'},
        {'op': 'test', 'path': '/metadata/labels/app.kubernetes.io~1managed-by', 'value': 'kaori'},
        {'op': 'test', 'path': '/metadata/labels/kaori.io~1tenant-id', 'value': 'tenant-1'},
    ]
    assert ops[-1] == {
        'op': 'add', 'path': '/metadata/labels/app.kubernetes.io~1managed-by',
        'value': 'platform-team',
    }
    removed = [op['path'] for op in ops if op['op'] == 'remove']
    assert len(removed) == 6
    assert '/metadata/labels/kaori.io~1resource-profile' in removed
    assert '/metadata/labels/kaori.io~1tenant-generation' in removed
    assert '/metadata/labels/example.com~1external' not in removed
    assert all(op['path'].startswith('/metadata/') for op in ops)
    assert all(op['op'] in {'test', 'remove', 'add'} for op in ops)
    assert not any('spec' in op['path'] for op in ops)
    assert resource == before


@pytest.mark.parametrize('owner', [
    'kaori', 'KAORI', 'system', 'system-admin', 'team/invalid',
    'name with space', '', 'x' * 64,
])
def test_unsafe_or_invalid_successor_is_rejected(owner):
    with pytest.raises(ValueError, match='successor label'):
        build_native_successor_handoff_patch(
            _component(), _resource(), tenant_id='tenant-1',
            verified_successor_owner=owner,
        )


@pytest.mark.parametrize('change', [
    lambda component, resource: component.update(uid='changed'),
    lambda component, resource: component.update(resource_version='28'),
    lambda component, resource: component.update(ownership='marker_conflict'),
    lambda component, resource: component.update(handoff='observe_only'),
    lambda component, resource: resource.metadata.labels.update({'kaori.io/tenant-id': 'foreign'}),
    lambda component, resource: resource.metadata.labels.update({'app.kubernetes.io/managed-by': 'external'}),
])
def test_stale_or_foreign_owned_component_is_not_a_transfer_target(change):
    component, resource = _component(), _resource()
    change(component, resource)
    with pytest.raises(ValueError):
        build_native_successor_handoff_patch(
            component, resource, tenant_id='tenant-1',
            verified_successor_owner='platform-team',
        )

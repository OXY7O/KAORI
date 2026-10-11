"""#1231 Capsule successor handback: pure negative and preservation checks.

Authored only while KAORI CI/CD, test and live provider gates are on HOLD.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_successor_handback import (
    _capsule_handback_scope,
    _handback_patch,
    _handback_snapshot,
    _verify_handback,
)


def _case():
    tenant = SimpleNamespace(
        id='tenant-1', cluster_id='cluster-1', generation=2,
        provider_reference='demo',
    )
    release = {
        'status': 'released', 'release_mode': 'managed_handoff',
        'provider_handoff_verified': True,
        'provider': 'capsule', 'tenant_id': tenant.id,
        'cluster_id': tenant.cluster_id, 'generation': tenant.generation,
        'plan_sha256': 'a' * 64, 'handoff_fingerprint': 'b' * 64,
        'successor_owner': 'platform-team', 'released_namespace_count': 1,
        'verified_resource_count': 4,
        'verified_components': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid',
             'resource_version': '11', 'state': 'preserved'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid',
             'resource_version': '15', 'state': 'provider_markers_transferred'},
            {'kind': 'ResourceQuota', 'namespace': 'demo-dev',
             'name': 'managed-quota', 'uid': 'quota-uid',
             'resource_version': '24', 'state': 'provider_markers_transferred'},
            {'kind': 'RoleBinding', 'namespace': 'demo-dev',
             'name': 'capsule-generated', 'uid': 'rb-uid',
             'resource_version': '7', 'state': 'preserved'},
        ],
    }
    return tenant, release


def _resource(*, name='demo-dev', uid='ns-uid', rv='15', kind='Namespace',
              owner='platform-team'):
    meta = SimpleNamespace(
        name=name, uid=uid, resource_version=rv,
        labels={
            'app.kubernetes.io/managed-by': owner,
            'capsule.clastix.io/tenant': 'demo',
            'external.example/owner': 'unmodified',
        },
        annotations={'external.example/keep': 'yes'},
        owner_references=[], finalizers=[], deletion_timestamp=None,
    )
    return SimpleNamespace(metadata=meta, spec={'quota': {'pods': 3}})


def test_capsule_handback_exact_scope_does_not_patch_cr_or_foreign_rbac():
    tenant, release = _case()
    cr, targets = _capsule_handback_scope(release=release, tenant=tenant)
    assert cr['uid'] == 'cr-uid'
    assert [(x['kind'], x['name']) for x in targets] == [
        ('ResourceQuota', 'managed-quota'),
        ('Namespace', 'demo-dev'),
    ]


@pytest.mark.parametrize('change', [
    lambda r: r.update(verified_resource_count=3),
    lambda r: r.update(released_namespace_count=2),
    lambda r: r['verified_components'].pop(0),
    lambda r: r['verified_components'].append(deepcopy(r['verified_components'][1])),
    lambda r: r['verified_components'][1].update(uid=''),
    lambda r: r['verified_components'][0].update(state='provider_markers_transferred'),
    lambda r: r['verified_components'][2].update(state='unknown'),
    lambda r: r['verified_components'][2].update(namespace='foreign-ns'),
    lambda r: r.update(provider_handoff_verified=False),
    lambda r: r.update(release_mode='observed_only'),
])
def test_capsule_handback_rejects_missing_duplicate_foreign_or_unverified_scope(change):
    tenant, release = _case()
    change(release)
    with pytest.raises((ValueError, TypeError)):
        _capsule_handback_scope(release=release, tenant=tenant)


def test_handback_json_patch_is_exact_cas_metadata_only():
    tenant, release = _case()
    _, targets = _capsule_handback_scope(release=release, tenant=tenant)
    ns = next(item for item in targets if item['kind'] == 'Namespace')
    before = _resource()
    patch = _handback_patch(before=before, item=ns, owner='platform-team')
    assert patch == [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'ns-uid'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '15'},
        {'op': 'test', 'path': '/metadata/labels',
         'value': dict(before.metadata.labels)},
        {'op': 'remove', 'path': '/metadata/labels/app.kubernetes.io~1managed-by'},
    ]
    assert all(op['path'].startswith('/metadata/') for op in patch)


def test_capsule_handback_preview_and_post_patch_preserve_policy_and_foreign_labels():
    tenant, release = _case()
    _, targets = _capsule_handback_scope(release=release, tenant=tenant)
    ns = next(item for item in targets if item['kind'] == 'Namespace')
    before = _resource()
    after = deepcopy(before)
    after.metadata.labels.pop('app.kubernetes.io/managed-by')
    # Admission preview can keep original RV.
    assert _verify_handback(
        before=before, after=after, item=ns,
        owner='platform-team', preview=True,
    ) == '15'
    after.metadata.resource_version = '16'
    assert _verify_handback(
        before=before, after=after, item=ns,
        owner='platform-team', preview=False,
    ) == '16'
    assert after.metadata.labels['external.example/owner'] == 'unmodified'


@pytest.mark.parametrize('mutate', [
    lambda a: a.metadata.labels.update({'foreign.example/drift': 'x'}),
    lambda a: setattr(a.metadata, 'uid', 'different'),
    lambda a: a.spec.update({'quota': {'pods': 100}}),
    lambda a: setattr(a.metadata, 'resource_version', ''),
])
def test_capsule_handback_rejects_unexpected_provider_readback(mutate):
    tenant, release = _case()
    ns = release['verified_components'][1]
    before = _resource()
    after = deepcopy(before)
    after.metadata.labels.pop('app.kubernetes.io/managed-by')
    after.metadata.resource_version = '16'
    mutate(after)
    with pytest.raises(ValueError):
        _verify_handback(
            before=before, after=after, item={**ns, 'namespace': 'demo-dev'},
            owner='platform-team', preview=False,
        )


def test_capsule_handback_refuses_stale_release_rv_or_kaori_marker():
    tenant, release = _case()
    ns = {**release['verified_components'][1], 'namespace': 'demo-dev'}
    with pytest.raises(ValueError, match='changed since Release'):
        _handback_snapshot(
            before=_resource(rv='17'), item=ns, owner='platform-team',
        )
    foreign = _resource()
    foreign.metadata.labels['kaori.io/tenant-id'] = 'unexpected'
    with pytest.raises(ValueError, match='changed since Release'):
        _handback_snapshot(
            before=foreign, item=ns, owner='platform-team',
        )

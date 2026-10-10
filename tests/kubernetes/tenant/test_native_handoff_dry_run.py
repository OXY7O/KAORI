from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.native_handoff_dry_run import (
    build_native_handoff_patch,
    dry_run_native_handoff_component,
    dry_run_native_release_handoff_committed,
)


def _component(kind: str = 'Namespace') -> dict[str, str]:
    return {
        'kind': kind, 'name': 'sandbox' if kind == 'Namespace' else 'limits',
        'namespace': 'sandbox', 'uid': 'uid-7', 'resource_version': '19',
        'handoff': 'external_acceptance_required',
        'ownership': 'kaori_marker_correlated',
    }


def _resource(kind: str = 'Namespace', *, uid: str = 'uid-7', rv: str = '19'):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='sandbox' if kind == 'Namespace' else 'limits',
            uid=uid, resource_version=rv,
            owner_references=[], finalizers=['example.com/keep'],
            generation=5, deletion_timestamp=None,
            deletion_grace_period_seconds=None,
            labels={
                'app.kubernetes.io/managed-by': 'kaori',
                'kaori.io/tenant-id': 'tenant-1',
                'kaori.io/environment': 'dev',
                'kaori.io/resource-profile': 'resource-profile-v2',
                'kaori.io/tenant-generation': '4',
                'kaori.io/profile-id': 'profile-v2',
                'example.com/other': 'preserved',
            },
        ),
        spec={'hard': {'requests.cpu': '2'}} if kind == 'ResourceQuota'
        else {'limits': ['8Gi']} if kind == 'LimitRange' else None,
    )


class _CoreApi:
    def __init__(self, kind='Namespace', *, tamper_spec=False, tamper_labels=False,
                 tamper_annotations=False, tamper_owner=False,
                 tamper_finalizers=False, persist=False):
        self.obj = _resource(kind)
        self.tamper_spec = tamper_spec
        self.tamper_labels = tamper_labels
        self.tamper_annotations = tamper_annotations
        self.tamper_owner = tamper_owner
        self.tamper_finalizers = tamper_finalizers
        self.persist = persist
        self.calls = []

    def _read(self):
        self.calls.append(('read',))
        return deepcopy(self.obj)

    def _patch(self, **kwargs):
        self.calls.append(('patch', kwargs))
        assert kwargs['dry_run'] == 'All'
        assert kwargs['_content_type'] == 'application/json-patch+json'
        assert kwargs['_request_timeout'] == 5
        patched = deepcopy(self.obj)
        for op in kwargs['body']:
            if op['op'] == 'remove':
                key = op['path'].split('/metadata/labels/')[1].replace('~1', '/').replace('~0', '~')
                patched.metadata.labels.pop(key)
        if self.tamper_spec:
            patched.spec = {'unexpected': True}
        if self.tamper_labels:
            patched.metadata.labels['example.com/other'] = 'modified'
        if self.tamper_annotations:
            patched.metadata.annotations = {'example.com/source': 'unexpected'}
        if self.tamper_owner:
            patched.metadata.owner_references = [{'kind': 'Namespace', 'name': 'foreign'}]
        if self.tamper_finalizers:
            patched.metadata.finalizers = []
        if self.persist:
            self.obj = deepcopy(patched)
        return patched

    def read_namespace(self, name, **kwargs):
        return self._read()

    def read_namespaced_resource_quota(self, name, namespace, **kwargs):
        return self._read()

    def read_namespaced_limit_range(self, name, namespace, **kwargs):
        return self._read()

    def patch_namespace(self, **kwargs):
        return self._patch(**kwargs)

    def patch_namespaced_resource_quota(self, **kwargs):
        return self._patch(**kwargs)

    def patch_namespaced_limit_range(self, **kwargs):
        return self._patch(**kwargs)


@pytest.mark.parametrize('kind', ['Namespace', 'ResourceQuota', 'LimitRange'])
def test_native_handoff_simulates_all_component_types_without_persisting(kind):
    core = _CoreApi(kind)
    before = deepcopy(core.obj)
    outcome = dry_run_native_handoff_component(
        core, _component(kind), tenant_id='tenant-1'
    )

    assert outcome['dry_run'] is True
    assert outcome['live_provider_unchanged'] is True
    assert outcome['spec_unchanged'] is True
    assert outcome['label_keys_to_release'] == [
        'app.kubernetes.io/managed-by',
        'kaori.io/tenant-id',
        'kaori.io/environment',
        'kaori.io/resource-profile',
        'kaori.io/tenant-generation',
        'kaori.io/profile-id',
    ]
    assert len([c for c in core.calls if c[0] == 'patch']) == 1
    assert core.obj == before


@pytest.mark.parametrize('kind', ['Namespace', 'ResourceQuota', 'LimitRange'])
def test_handoff_dry_run_releases_real_profile_label_without_legacy_alias(kind):
    core = _CoreApi(kind)
    core.obj.metadata.labels.pop('kaori.io/profile-id')
    core.obj.metadata.labels.pop('kaori.io/tenant-generation')
    before = deepcopy(core.obj)
    receipt = dry_run_native_handoff_component(
        core, _component(kind), tenant_id='tenant-1',
    )
    assert 'kaori.io/resource-profile' in receipt['label_keys_to_release']
    assert receipt['spec_unchanged'] is True
    assert receipt['live_provider_unchanged'] is True
    assert core.obj == before


def test_json_patch_tests_uid_version_owner_before_removing_only_kaori_metadata():
    ops = build_native_handoff_patch(
        _component(), _resource(), tenant_id='tenant-1',
    )
    assert ops[:4] == [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'uid-7'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '19'},
        {'op': 'test', 'path': '/metadata/labels/app.kubernetes.io~1managed-by', 'value': 'kaori'},
        {'op': 'test', 'path': '/metadata/labels/kaori.io~1tenant-id', 'value': 'tenant-1'},
    ]
    assert all(op['path'].startswith('/metadata/') for op in ops)
    assert all(op['op'] in ('test', 'remove') for op in ops)
    assert not any('spec' in op['path'] for op in ops)


@pytest.mark.parametrize('change', [
    lambda component, resource: component.update(uid='different'),
    lambda component, resource: component.update(resource_version='2'),
    lambda component, resource: component.update(handoff='observe_only'),
    lambda component, resource: component.update(ownership='marker_conflict'),
    lambda component, resource: resource.metadata.labels.update(
        {'kaori.io/tenant-id': 'another-tenant'}
    ),
    lambda component, resource: resource.metadata.labels.update(
        {'app.kubernetes.io/managed-by': 'external'}
    ),
])
def test_native_patch_fails_closed_on_missing_authority_or_changed_identity(change):
    component, resource = _component(), _resource()
    change(component, resource)
    with pytest.raises(ValueError):
        build_native_handoff_patch(component, resource, tenant_id='tenant-1')


def test_dry_run_rejects_mutating_admission_or_live_provider_side_effect():
    core = _CoreApi('ResourceQuota', tamper_spec=True)
    with pytest.raises(ValueError, match='spec'):
        dry_run_native_handoff_component(
            core, _component('ResourceQuota'), tenant_id='tenant-1'
        )
    core = _CoreApi('Namespace', tamper_labels=True)
    with pytest.raises(ValueError, match='unrelated Kubernetes labels'):
        dry_run_native_handoff_component(
            core, _component(), tenant_id='tenant-1'
        )
    core = _CoreApi('Namespace', tamper_annotations=True)
    with pytest.raises(ValueError, match='annotations'):
        dry_run_native_handoff_component(
            core, _component(), tenant_id='tenant-1'
        )
    core = _CoreApi('Namespace', tamper_owner=True)
    with pytest.raises(ValueError, match='ownerReferences'):
        dry_run_native_handoff_component(core, _component(), tenant_id='tenant-1')
    core = _CoreApi('Namespace', tamper_finalizers=True)
    with pytest.raises(ValueError, match='finalizers'):
        dry_run_native_handoff_component(core, _component(), tenant_id='tenant-1')
    core = _CoreApi('Namespace', persist=True)
    with pytest.raises(ValueError, match='live state changed'):
        dry_run_native_handoff_component(
            core, _component(), tenant_id='tenant-1'
        )



def test_native_dry_run_rejects_colluding_or_mismatched_approval(monkeypatch):
    from app.kubernetes.tenant import native_handoff_dry_run as module

    plan = {
        'tenant_id': 'tenant-a',
        'requested_by': 21,
        'plan_sha256': 'a' * 64,
        'handoff_fingerprint': 'fingerprint',
    }
    approval = {
        'plan_sha256': 'a' * 64,
        'status': 'acknowledged_pending_provider_handoff',
        'requested_by': 21,
        'approved_by': 21,
        'handoff_fingerprint': 'fingerprint',
        'approved_at': '2026-10-09T00:00:00+00:00',
        'provider_handoff_verified': False,
        'release_authorized': False,
    }
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: approval)
    monkeypatch.setattr(module, '_plan_hash', lambda _: 'a' * 64)
    monkeypatch.setattr(module, '_checked_recently', lambda _: True)
    with pytest.raises(ValueError, match='independently approved'):
        dry_run_native_release_handoff_committed(
            tenant_id='tenant-a', actor_user_id=32, plan_sha256='a' * 64
        )

    approval['approved_by'] = 22
    approval['handoff_fingerprint'] = 'outdated'
    with pytest.raises(ValueError, match='independently approved'):
        dry_run_native_release_handoff_committed(
            tenant_id='tenant-a', actor_user_id=32, plan_sha256='a' * 64
        )

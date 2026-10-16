"""Capsule G2/G3 metadata-only quota, limit and RBAC handoff source cases.

AUTHORED ONLY: no pytest, Kubernetes dry-run, provider PATCH, CI/CD, SQL,
DevContainer QA or UAT are run under operator gate HOLD (#1229).
"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_handoff_contract import (
    build_capsule_related_metadata_handoff_patch,
    classify_capsule_related_metadata_readback,
    verify_capsule_related_metadata_preview,
)
from app.kubernetes.tenant.capsule_handoff_dry_run import preview_capsule_related_handoff_with_provider
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    classify_capsule_related_resource,
)

_KINDS = ('ResourceQuota', 'LimitRange', 'RoleBinding')
_TENANT = 'tenant-uuid'
_NS = 'demo-dev'
_CAPSULE = 'demo'
_CAPSULE_UID = 'capsule-uid'
_SUCCESSOR = 'platform-team'


def _resource(kind, *, owner_refs=None, labels=None):
    markers = {
        'app.kubernetes.io/managed-by': 'kaori',
        'kaori.io/tenant-id': _TENANT,
        'kaori.io/environment': 'development',
        'foreign.example/keep': 'yes',
        'capsule.clastix.io/tenant': _CAPSULE,
    }
    if kind == 'RoleBinding':
        markers.pop('kaori.io/environment')
        markers['kaori.io/access-grant'] = 'grant-id'
    if labels is not None:
        markers = labels
    meta = SimpleNamespace(
        name='resource-1',
        uid='uid-1',
        resource_version='7',
        namespace=_NS,
        labels=markers,
        annotations={'external.example/note': 'keep'},
        owner_references=(
            owner_refs
            if owner_refs is not None
            else [
                {
                    'kind': 'Tenant',
                    'apiVersion': 'capsule.clastix.io/v1beta2',
                    'name': _CAPSULE,
                    'uid': _CAPSULE_UID,
                }
            ]
        ),
        finalizers=['foreign.example/preserve'],
    )
    resource = SimpleNamespace(metadata=meta)
    if kind == 'ResourceQuota':
        resource.spec = {'hard': {'requests.cpu': '2', 'requests.memory': '2Gi'}}
    elif kind == 'LimitRange':
        resource.spec = {'limits': [{'type': 'Container', 'max': {'memory': '1Gi'}}]}
    else:
        resource.role_ref = {
            'kind': 'ClusterRole',
            'name': 'view',
            'apiGroup': 'rbac.authorization.k8s.io',
        }
        resource.subjects = [{'kind': 'ServiceAccount', 'name': 'existing', 'namespace': _NS}]
    return resource


def _source(kind, obj):
    record, blockers = classify_capsule_related_resource(
        resource=obj,
        kind=kind,
        namespace=_NS,
        tenant_id=_TENANT,
        capsule_name=_CAPSULE,
        capsule_uid=_CAPSULE_UID,
    )
    assert record['origin'] == 'kaori_correlated'
    assert record['mutation_authorized'] == 'false'
    assert len(blockers) == 1 and 'handoff' in blockers[0]
    return record


def _args(kind, obj, *, keys=None):
    return {
        'record': _source(kind, obj),
        'before': obj,
        'kind': kind,
        'namespace': _NS,
        'tenant_id': _TENANT,
        'capsule_name': _CAPSULE,
        'capsule_uid': _CAPSULE_UID,
        'successor_owner': _SUCCESSOR,
        'approved_label_keys': (
            keys
            if keys is not None
            else [
                key
                for key in obj.metadata.labels
                if key.startswith('kaori.io/') or key == 'app.kubernetes.io/managed-by'
            ]
        ),
    }


def _after(kind, before, *, resource_version='8'):
    after = deepcopy(before)
    after.metadata.resource_version = resource_version
    after.metadata.labels = {
        key: val
        for key, val in after.metadata.labels.items()
        if not key.startswith('kaori.io/') and key != 'app.kubernetes.io/managed-by'
    }
    after.metadata.labels['app.kubernetes.io/managed-by'] = _SUCCESSOR
    return after


@pytest.mark.parametrize('kind', _KINDS)
def test_related_patch_only_tests_uid_rv_labels_then_transfers_approved_kaori_keys(kind):
    before = _resource(kind)
    args = _args(kind, before)
    patch = build_capsule_related_metadata_handoff_patch(**args)
    assert patch[:3] == [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'uid-1'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '7'},
        {'op': 'test', 'path': '/metadata/labels', 'value': before.metadata.labels},
    ]
    removed = {op['path'] for op in patch if op['op'] == 'remove'}
    assert removed == {
        '/metadata/labels/' + key.replace('~', '~0').replace('/', '~1') for key in args['approved_label_keys']
    }
    assert patch[-1] == {
        'op': 'add',
        'path': '/metadata/labels/app.kubernetes.io~1managed-by',
        'value': _SUCCESSOR,
    }
    assert not any(
        'spec' in op['path']
        or 'roleRef' in op['path']
        or 'subject' in op['path']
        or 'finalizer' in op['path']
        or 'annotation' in op['path']
        or 'ownerReference' in op['path']
        for op in patch
    )
    assert before.metadata.labels['app.kubernetes.io/managed-by'] == 'kaori'
    assert all(op['op'] in ('test', 'remove', 'add') for op in patch)


@pytest.mark.parametrize('kind', _KINDS)
def test_related_server_dryrun_preview_checks_full_invariants_without_rv_change(kind):
    before = _resource(kind)
    args = _args(kind, before)
    preview = _after(kind, before, resource_version='7')
    result = verify_capsule_related_metadata_preview(
        **args,
        preview=preview,
    )
    assert result['status'] == 'dry_run_shape_checked_not_admitted'
    assert result['provider_execution_admitted'] is False
    assert result['provider_mutation_performed'] is False
    assert len(result['preview_sha256']) == 64
    assert 'existing' not in str(result)  # never expose RBAC subjects


@pytest.mark.parametrize('kind', _KINDS)
def test_related_readback_requires_new_rv_and_exactly_transferred_labels(kind):
    before = _resource(kind)
    args = _args(kind, before)
    pending = classify_capsule_related_metadata_readback(**args, current=deepcopy(before))
    assert pending['state'] == 'pending_provider_transfer'
    transferred = classify_capsule_related_metadata_readback(
        **args,
        current=_after(kind, before),
    )
    assert transferred['state'] == 'provider_markers_transferred'
    assert transferred['policy_preserved'] is True
    assert transferred['owner_annotations_finalizers_preserved'] is True
    assert transferred['provider_snapshot_authenticity_verified'] is False
    assert transferred['provider_handoff_verified'] is False
    assert transferred['auto_retry_authorized'] is False
    assert transferred['release_authorized'] is False


@pytest.mark.parametrize('kind', _KINDS)
def test_same_rv_transferred_labels_or_new_rv_without_handoff_is_ambiguous(kind):
    before = _resource(kind)
    args = _args(kind, before)
    with pytest.raises(ValueError, match='partially transferred'):
        classify_capsule_related_metadata_readback(
            **args,
            current=_after(kind, before, resource_version='7'),
        )
    unchanged_labels = deepcopy(before)
    unchanged_labels.metadata.resource_version = '8'
    with pytest.raises(ValueError, match='partially transferred'):
        classify_capsule_related_metadata_readback(**args, current=unchanged_labels)


@pytest.mark.parametrize('kind', _KINDS)
def test_partial_consent_scope_and_foreign_labels_never_enter_patch(kind):
    before = _resource(kind)
    args = _args(kind, before)
    args['approved_label_keys'] = ['app.kubernetes.io/managed-by']
    with pytest.raises(ValueError, match='partial'):
        build_capsule_related_metadata_handoff_patch(**args)
    args = _args(kind, before)
    args['approved_label_keys'].append('foreign.example/keep')
    with pytest.raises(ValueError, match='partial'):
        build_capsule_related_metadata_handoff_patch(**args)
    args = _args(kind, before)
    args['approved_label_keys'].append('kaori.io/unadmitted')
    with pytest.raises(ValueError, match='partial'):
        build_capsule_related_metadata_handoff_patch(**args)


@pytest.mark.parametrize('kind', _KINDS)
def test_stale_source_uid_rv_metadata_policy_and_owner_claim_block_g2(kind):
    before = _resource(kind)
    args = _args(kind, before)
    args['record']['resource_version'] = 'prior-rv'
    with pytest.raises(ValueError):
        build_capsule_related_metadata_handoff_patch(**args)
    args = _args(kind, before)
    before.metadata.annotations['external.example/note'] = 'changed'
    with pytest.raises(ValueError):
        build_capsule_related_metadata_handoff_patch(**args)
    before = _resource(
        kind,
        owner_refs=[
            {
                'kind': 'ConfigMap',
                'name': 'foreign-controller',
                'uid': 'foreign-uid',
            }
        ],
    )
    record, findings = classify_capsule_related_resource(
        resource=before,
        kind=kind,
        namespace=_NS,
        tenant_id=_TENANT,
        capsule_name=_CAPSULE,
        capsule_uid=_CAPSULE_UID,
    )
    assert record['origin'] == 'ambiguous_kaori'
    assert findings


@pytest.mark.parametrize('kind', _KINDS)
def test_related_readback_fails_closed_on_policy_annotations_owner_or_finalizer_drift(kind):
    before = _resource(kind)
    args = _args(kind, before)
    if kind == 'RoleBinding':
        changed = _after(kind, before)
        changed.subjects[0]['name'] = 'foreign-subject'
    else:
        changed = _after(kind, before)
        changed.spec['hijack'] = 'not-approved'
    with pytest.raises(ValueError, match='policy'):
        classify_capsule_related_metadata_readback(**args, current=changed)
    for changed_field, value in [
        ('annotations', {'external.example/note': 'changed'}),
        ('owner_references', []),
        ('finalizers', ['other.example/finalizer']),
    ]:
        changed = _after(kind, before)
        setattr(changed.metadata, changed_field, value)
        with pytest.raises(ValueError, match='owner, annotations or finalizers'):
            classify_capsule_related_metadata_readback(**args, current=changed)


@pytest.mark.parametrize('kind', _KINDS)
def test_related_readback_rejects_unauthorized_extra_metadata_change(kind):
    before = _resource(kind)
    args = _args(kind, before)
    changed = _after(kind, before)
    changed.metadata.labels['foreign.example/keep'] = 'tampered'
    with pytest.raises(ValueError, match='partially transferred'):
        classify_capsule_related_metadata_readback(**args, current=changed)
    changed = _after(kind, before)
    changed.metadata.uid = 'replaced-uid'
    with pytest.raises(ValueError, match='identity'):
        classify_capsule_related_metadata_readback(**args, current=changed)


def test_rolebinding_requires_original_exact_grant_and_role_contract():
    before = _resource('RoleBinding')
    args = _args('RoleBinding', before)
    args['record'].pop('grant_scope_sha256')
    with pytest.raises(ValueError):
        build_capsule_related_metadata_handoff_patch(**args)
    args = _args('RoleBinding', before)
    before.subjects[0]['name'] = 'changed-user'
    with pytest.raises(ValueError):
        build_capsule_related_metadata_handoff_patch(**args)


def test_source_preview_never_exposes_raw_provider_policy_or_secret_material():
    before = _resource('RoleBinding')
    before.subjects = [{'kind': 'User', 'name': 'SENSITIVE-PRINCIPAL'}]
    args = _args('RoleBinding', before)
    result = verify_capsule_related_metadata_preview(
        **args,
        preview=_after('RoleBinding', before),
    )
    assert 'SENSITIVE-PRINCIPAL' not in str(result)
    assert 'subjects' not in str(result)
    assert result['provider_execution_admitted'] is False


def test_rolebinding_nonconsentable_kaori_profile_label_is_blocked():
    before = _resource('RoleBinding')
    before.metadata.labels['kaori.io/resource-profile'] = 'stale-profile'
    args = _args('RoleBinding', before)
    with pytest.raises(ValueError, match='partial, unsafe'):
        build_capsule_related_metadata_handoff_patch(**args)


@pytest.mark.parametrize('kind', _KINDS)
def test_related_preview_and_readback_refuse_changed_namespace_metadata(kind):
    before = _resource(kind)
    args = _args(kind, before)
    altered = _after(kind, before)
    altered.metadata.namespace = 'foreign-ns'
    with pytest.raises(ValueError):
        verify_capsule_related_metadata_preview(**args, preview=altered)
    with pytest.raises(ValueError):
        classify_capsule_related_metadata_readback(**args, current=altered)


@pytest.mark.parametrize('kind', _KINDS)
def test_related_real_server_preview_dispatch_is_nonmutating_and_per_kind(kind):
    before = _resource(kind)
    record = _source(kind, before)
    args = _args(kind, before)
    seen = []

    def read(*, name, namespace, _request_timeout):
        assert name == 'resource-1' and namespace == _NS
        assert _request_timeout == 5
        seen.append('GET')
        return deepcopy(before)

    def patch(*, name, namespace, body, dry_run, _content_type, _request_timeout):
        assert (name, namespace) == ('resource-1', _NS)
        assert dry_run == 'All'
        assert _content_type == 'application/json-patch+json'
        assert _request_timeout == 5
        assert body[0] == {'op': 'test', 'path': '/metadata/uid', 'value': 'uid-1'}
        assert body[1] == {
            'op': 'test',
            'path': '/metadata/resourceVersion',
            'value': '7',
        }
        seen.append('dryRun=All')
        return _after(kind, before, resource_version='7')

    methods = {
        'ResourceQuota': ('read_namespaced_resource_quota', 'patch_namespaced_resource_quota'),
        'LimitRange': ('read_namespaced_limit_range', 'patch_namespaced_limit_range'),
        'RoleBinding': ('read_namespaced_role_binding', 'patch_namespaced_role_binding'),
    }
    api = SimpleNamespace(**dict(zip(methods[kind], [read, patch])))
    receipt = preview_capsule_related_handoff_with_provider(
        core=api,
        rbac=api,
        record=record,
        namespace=_NS,
        tenant_id=_TENANT,
        capsule_name=_CAPSULE,
        capsule_uid=_CAPSULE_UID,
        successor_owner=_SUCCESSOR,
        approved_label_keys=args['approved_label_keys'],
    )
    assert seen == ['GET', 'dryRun=All', 'GET']
    assert receipt['live_resource_unchanged'] is True
    assert receipt['provider_mutation_performed'] is False
    assert receipt['provider_execution_admitted'] is False
    assert receipt['release_authorized'] is False
    assert before.metadata.resource_version == '7'


@pytest.mark.parametrize('kind', _KINDS)
def test_related_server_preview_refuses_concurrent_mutation_after_dryrun(kind):
    before = _resource(kind)
    args = _args(kind, before)
    reads = []

    def read(**_kwargs):
        reads.append(True)
        current = deepcopy(before)
        if len(reads) == 2:
            current.metadata.resource_version = 'new-concurrent-rv'
        return current

    def patch(**kwargs):
        assert kwargs['dry_run'] == 'All'
        return _after(kind, before, resource_version='7')

    methods = {
        'ResourceQuota': ('read_namespaced_resource_quota', 'patch_namespaced_resource_quota'),
        'LimitRange': ('read_namespaced_limit_range', 'patch_namespaced_limit_range'),
        'RoleBinding': ('read_namespaced_role_binding', 'patch_namespaced_role_binding'),
    }
    api = SimpleNamespace(**dict(zip(methods[kind], [read, patch])))
    with pytest.raises(ValueError, match='changed during dry-run'):
        preview_capsule_related_handoff_with_provider(
            core=api,
            rbac=api,
            record=args['record'],
            namespace=_NS,
            tenant_id=_TENANT,
            capsule_name=_CAPSULE,
            capsule_uid=_CAPSULE_UID,
            successor_owner=_SUCCESSOR,
            approved_label_keys=args['approved_label_keys'],
        )

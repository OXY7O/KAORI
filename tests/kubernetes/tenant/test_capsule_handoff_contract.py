"""#1229 Capsule pure metadata transfer and fail-closed preservation regressions.

Author-only during review HOLD: these tests must not be executed until authorization.
"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_handoff_contract import (
    build_capsule_namespace_handoff_patch,
    capsule_preservation_digest,
    validate_capsule_handoff_scope,
    verify_capsule_cr_preserved,
    verify_capsule_namespace_preview,
)
from app.kubernetes.tenant.release_handoff_inventory import _capsule_spec_sha256


def _components():
    return [
        {
            'kind': 'CapsuleTenant',
            'name': 'demo',
            'uid': 'cr-uid',
            'resource_version': '22',
            'authority': 'capsule',
            'handoff': 'external_acceptance_required',
            'ownership': 'external_or_unattributed',
            'capsule_spec_sha256': _capsule_spec_sha256({'resourceQuotas': {'scope': 'Tenant'}}),
        },
        {
            'kind': 'Namespace',
            'name': 'demo-dev',
            'namespace': 'demo-dev',
            'uid': 'ns-uid',
            'resource_version': '7',
            'authority': 'capsule',
            'handoff': 'external_acceptance_required',
            'ownership': 'kaori_marker_correlated',
        },
    ]


def _namespace(*, labels=None, rv='7', owner=None):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='demo-dev',
            uid='ns-uid',
            resource_version=rv,
            labels=labels
            if labels is not None
            else {
                'app.kubernetes.io/managed-by': 'kaori',
                'kaori.io/tenant-id': 'tenant-uuid',
                'kaori.io/environment': 'dev',
                'capsule.clastix.io/tenant': 'demo',
                'foreign.example/retained': 'yes',
            },
            annotations={'foreign.example/external': 'preserve'},
            owner_references=[{'kind': 'Tenant', 'name': 'demo', 'uid': 'cr-uid'}],
            finalizers=['capsule.clastix.io/namespace-protection'],
            generation=1,
            deletion_timestamp=None,
            deletion_grace_period_seconds=None,
        ),
        spec={'finalizers': ['kubernetes']},
    )


def test_scope_accepts_exact_cr_and_namespace_only():
    cr, namespaces = validate_capsule_handoff_scope(_components())
    assert cr['uid'] == 'cr-uid'
    assert [item['name'] for item in namespaces] == ['demo-dev']


@pytest.mark.parametrize(
    'change',
    [
        lambda items: items.append(deepcopy(items[1])),
        lambda items: items.pop(0),
        lambda items: items[0].update(capsule_spec_sha256=''),
        lambda items: items[0].update(kind='Secret'),
        lambda items: items[0].update(ownership='marker_conflict'),
        lambda items: items[1].update(namespace='not-approved'),
        lambda items: items[1].update(authority='native_kubernetes'),
        lambda items: items[1].update(uid=''),
        lambda items: items[1].update(handoff='owner_review_required'),
    ],
)
def test_unsupported_or_ambiguous_scope_fails_closed(change):
    components = _components()
    change(components)
    with pytest.raises(ValueError):
        validate_capsule_handoff_scope(components)


def test_patch_is_uid_rv_conditional_and_only_changes_kaori_metadata():
    patch = build_capsule_namespace_handoff_patch(
        _components()[1],
        _namespace(),
        tenant_id='tenant-uuid',
        capsule_tenant_name='demo',
        verified_successor_owner='platform-team',
    )
    assert patch[:3] == [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'ns-uid'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '7'},
        {'op': 'test', 'path': '/metadata/labels', 'value': _namespace().metadata.labels},
    ]
    assert patch[-1] == {
        'op': 'add',
        'path': '/metadata/labels/app.kubernetes.io~1managed-by',
        'value': 'platform-team',
    }
    paths = [entry['path'] for entry in patch if entry['op'] == 'remove']
    assert '/metadata/labels/kaori.io~1tenant-id' in paths
    assert not any('capsule.clastix.io' in entry['path'] for entry in patch)
    assert not any(entry['path'].startswith('/spec') for entry in patch)
    assert not any('ownerReferences' in entry['path'] for entry in patch)
    assert not any('finalizers' in entry['path'] for entry in patch)


@pytest.mark.parametrize(
    'change',
    [
        lambda ns: setattr(ns.metadata, 'uid', 'recreated-uid'),
        lambda ns: setattr(ns.metadata, 'resource_version', '8'),
        lambda ns: ns.metadata.labels.update({'app.kubernetes.io/managed-by': 'someone-else'}),
        lambda ns: ns.metadata.labels.update({'kaori.io/tenant-id': 'foreign-tenant'}),
        lambda ns: ns.metadata.labels.update({'capsule.clastix.io/tenant': 'other'}),
        lambda ns: ns.metadata.labels.update({'projectcapsule.dev/tenant': 'other'}),
        lambda ns: ns.metadata.labels.pop('capsule.clastix.io/tenant'),
        lambda ns: ns.metadata.labels.update({'kaori.io/new-control': '1'}),
    ],
)
def test_refuse_identity_claim_membership_or_unknown_marker_changes(change):
    namespace = _namespace()
    change(namespace)
    with pytest.raises(ValueError):
        build_capsule_namespace_handoff_patch(
            _components()[1],
            namespace,
            tenant_id='tenant-uuid',
            capsule_tenant_name='demo',
            verified_successor_owner='platform-team',
        )


@pytest.mark.parametrize('successor', ['kaori', 'system:admin', '', '../escape', 'x' * 64])
def test_unverified_or_invalid_successor_is_rejected(successor):
    with pytest.raises(ValueError):
        build_capsule_namespace_handoff_patch(
            _components()[1],
            _namespace(),
            tenant_id='tenant-uuid',
            capsule_tenant_name='demo',
            verified_successor_owner=successor,
        )


def test_capsule_cr_preservation_checks_entire_spec_without_mutation():
    cr = _components()[0]
    provider = {
        'metadata': {
            'name': 'demo',
            'uid': 'cr-uid',
            'resourceVersion': '22',
            'labels': {'capsule.clastix.io/policy': 'native'},
        },
        'spec': {'resourceQuotas': {'scope': 'Tenant'}},
    }
    receipt = verify_capsule_cr_preserved(cr, provider)
    assert receipt['provider_spec_preserved'] is True
    assert receipt['provider_mutation_performed'] is False
    provider['spec']['resourceQuotas']['scope'] = 'Namespace'
    with pytest.raises(ValueError, match='spec'):
        verify_capsule_cr_preserved(cr, provider)


def test_cr_kaori_control_markers_require_independent_authority_review():
    cr = _components()[0]
    provider = {
        'metadata': {
            'name': 'demo',
            'uid': 'cr-uid',
            'resourceVersion': '22',
            'labels': {'app.kubernetes.io/managed-by': 'kaori'},
        },
        'spec': {'resourceQuotas': {'scope': 'Tenant'}},
    }
    with pytest.raises(ValueError, match='KAORI-owned'):
        verify_capsule_cr_preserved(cr, provider)


def test_dry_run_must_preserve_capsule_owner_finalizers_spec_and_foreign_labels():
    before = _namespace()
    preview = deepcopy(before)
    for key in ('app.kubernetes.io/managed-by', 'kaori.io/tenant-id', 'kaori.io/environment'):
        preview.metadata.labels.pop(key)
    preview.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
    verify_capsule_namespace_preview(before=before, preview=preview, successor_owner='platform-team')
    assert capsule_preservation_digest(before) == capsule_preservation_digest(preview)
    preview.spec['finalizers'] = []
    with pytest.raises(ValueError, match='provider-owned'):
        verify_capsule_namespace_preview(before=before, preview=preview, successor_owner='platform-team')


def test_foreign_annotation_or_owner_ref_drift_is_not_an_admitted_preview():
    before = _namespace()
    preview = deepcopy(before)
    for key in ('app.kubernetes.io/managed-by', 'kaori.io/tenant-id', 'kaori.io/environment'):
        preview.metadata.labels.pop(key)
    preview.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
    preview.metadata.annotations['foreign.example/external'] = 'changed'
    with pytest.raises(ValueError):
        verify_capsule_namespace_preview(before=before, preview=preview, successor_owner='platform-team')
    preview = deepcopy(before)
    for key in ('app.kubernetes.io/managed-by', 'kaori.io/tenant-id', 'kaori.io/environment'):
        preview.metadata.labels.pop(key)
    preview.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
    preview.metadata.owner_references = []
    with pytest.raises(ValueError):
        verify_capsule_namespace_preview(before=before, preview=preview, successor_owner='platform-team')

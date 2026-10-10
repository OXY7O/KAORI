"""Provider read-back classification tests for guarded Native handoff recovery."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.native_handoff_dry_run import (
    _retained_provider_metadata, _spec, _stable_sha256,
)
from app.kubernetes.tenant.native_handoff_recovery import (
    classify_native_handoff_component, summarize_native_handoff_recovery,
)


def _provider(*, kind='Namespace', name='dev', rv='12', manager='kaori', uid='uid-a'):
    labels = {
        'app.kubernetes.io/managed-by': manager,
        'example.com/external': 'unchanged',
    }
    if manager == 'kaori':
        labels.update({
            'kaori.io/tenant-id': 'tenant-a',
            'kaori.io/environment': 'development',
            'kaori.io/profile-id': 'profile-v2',
        })
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=name, uid=uid, resource_version=rv, labels=labels,
            annotations={'example.com/audit': 'retain'},
            owner_references=[], finalizers=['protect'], generation=1,
            deletion_timestamp=None, deletion_grace_period_seconds=None,
        ),
        spec={'hard': {'limits.cpu': '8', 'limits.memory': '16Gi'}} if kind != 'Namespace' else None,
    )


def _preview(*, kind='Namespace', name='dev', namespace='dev'):
    initial = _provider(kind=kind, name=name)
    return {
        'namespace': namespace, 'kind': kind, 'name': name,
        'uid': 'uid-a', 'resource_version': '12',
        'operation': 'metadata_only_json_patch_dry_run',
        'dry_run': True,
        'live_provider_unchanged': True,
        'spec_sha256': _stable_sha256(_spec(initial)),
        'retained_metadata_sha256': _stable_sha256(_retained_provider_metadata(initial)),
        'label_keys_to_release': [
            'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
            'kaori.io/environment', 'kaori.io/profile-id',
        ],
    }


@pytest.mark.parametrize('kind', ['Namespace', 'ResourceQuota', 'LimitRange'])
def test_exact_unchanged_provider_is_pending_without_release_authority(kind):
    result = classify_native_handoff_component(
        before=_preview(kind=kind), current=_provider(kind=kind),
        tenant_id='tenant-a', successor_owner='platform-team',
    )
    assert result['state'] == 'pending_provider_transfer'
    assert result['spec_preserved'] is True


def test_mixed_transferred_and_pending_requires_recovery_but_never_auto_resume():
    preview = [_preview(), _preview(kind='ResourceQuota', name='quota')]
    live = {
        ('dev', 'Namespace', 'dev', 'uid-a'): _provider(rv='13', manager='platform-team'),
        ('dev', 'ResourceQuota', 'quota', 'uid-a'): _provider(kind='ResourceQuota', name='quota'),
    }
    result = summarize_native_handoff_recovery(
        previewed_components=preview, live_components=live,
        tenant_id='tenant-a', successor_owner='platform-team',
    )
    assert result['status'] == 'partial_handoff_recovery_required'
    assert result['transferred_count'] == 1
    assert result['pending_count'] == 1
    assert result['resume_authorized'] is False
    assert result['release_authorized'] is False


def test_complete_provider_marker_transfer_is_not_trusted_successor_consent():
    preview = [_preview()]
    live = {('dev', 'Namespace', 'dev', 'uid-a'): _provider(rv='13', manager='platform-team')}
    outcome = summarize_native_handoff_recovery(
        previewed_components=preview, live_components=live,
        tenant_id='tenant-a', successor_owner='platform-team',
    )
    assert outcome['status'] == 'provider_markers_transferred_consent_unverified'
    assert outcome['successor_consent_verified'] is False
    assert outcome['release_authorized'] is False


@pytest.mark.parametrize('change', [
    lambda obj: setattr(obj.metadata, 'uid', 'replaced'),
    lambda obj: setattr(obj.metadata, 'resource_version', '12'),
    lambda obj: obj.metadata.labels.update({'kaori.io/tenant-id': 'other'}),
    lambda obj: obj.metadata.labels.update({'example.com/external': 'modified'}),
    lambda obj: obj.metadata.annotations.update({'foreign': 'added'}),
    lambda obj: setattr(obj.metadata, 'finalizers', []),
    lambda obj: setattr(obj, 'spec', {'hard': {'limits.cpu': '20'}}),
])
def test_unverifiable_or_changed_provider_is_blocked(change):
    current = deepcopy(_provider(rv='13', manager='platform-team'))
    change(current)
    with pytest.raises(ValueError):
        classify_native_handoff_component(
            before=_preview(), current=current, tenant_id='tenant-a',
            successor_owner='platform-team',
        )


def test_unexpected_extra_resource_or_duplicate_preview_is_blocked():
    preview = [_preview()]
    live = {('dev', 'Namespace', 'dev', 'uid-a'): _provider()}
    with pytest.raises(ValueError, match='inventory'):
        summarize_native_handoff_recovery(
            previewed_components=preview * 2, live_components=live,
            tenant_id='tenant-a', successor_owner='platform-team',
        )
    with pytest.raises(ValueError, match='inventory'):
        summarize_native_handoff_recovery(
            previewed_components=preview,
            live_components={**live, ('dev', 'LimitRange', 'extra', 'uid-z'): _provider()},
            tenant_id='tenant-a', successor_owner='platform-team',
        )


def test_preview_without_canonical_dry_run_proof_cannot_be_classified():
    before = _preview()
    before['dry_run'] = False
    with pytest.raises(ValueError, match='passing Native'):
        classify_native_handoff_component(
            before=before, current=_provider(), tenant_id='tenant-a',
            successor_owner='platform-team',
        )

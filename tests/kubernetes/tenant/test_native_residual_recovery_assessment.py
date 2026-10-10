"""Issue #1129: legacy Native Handback residue assessment is read-only."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.native_handoff_dry_run import (
    _retained_provider_metadata,
    _spec,
    _stable_sha256,
)
from app.kubernetes.tenant.native_residual_recovery_assessment import (
    _index_scope,
    _legacy_retained_metadata,
    inspect_legacy_profile_residue_component,
)


def resource(kind='Namespace', *, profile='profile-uuid', rv='58'):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='uat-demo' if kind == 'Namespace' else 'tenant-resource-quota',
            uid='uid-ns' if kind == 'Namespace' else 'uid-quota',
            resource_version=rv,
            labels={
                'environment': 'uat',
                'kaori.io/resource-profile': profile,
                'kubernetes.io/metadata.name': (
                    'uat-demo' if kind == 'Namespace' else 'tenant-resource-quota'
                ),
            },
            annotations={'external.io/retained': 'yes'},
            owner_references=[], finalizers=['external.io/finalizer'],
            generation=1, deletion_timestamp=None,
            deletion_grace_period_seconds=None,
        ),
        spec=None if kind == 'Namespace' else {
            'hard': {
                'requests.cpu': '2',
                'requests.memory': '4Gi',
                'limits.cpu': '4',
                'limits.memory': '8Gi',
            },
        },
    )


def evidence(live, *, kind='Namespace'):
    labels = dict(live.metadata.labels)
    labels.update({
        'app.kubernetes.io/managed-by': 'kaori',
        'kaori.io/tenant-id': 'tenant-1',
        'kaori.io/environment': 'uat',
    })
    before = deepcopy(live)
    before.metadata.labels = labels
    namespace = 'uat-demo'
    preview = {
        'kind': kind,
        'namespace': namespace,
        'name': live.metadata.name,
        'uid': live.metadata.uid,
        'resource_version': '40',
        'operation': 'metadata_only_json_patch_dry_run',
        'dry_run': True,
        'spec_unchanged': True,
        'live_provider_unchanged': True,
        'label_keys_to_release': [
            'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
            'kaori.io/environment',
        ],
        'spec_sha256': _stable_sha256(_spec(before)),
        'retained_metadata_sha256': _stable_sha256(_legacy_retained_metadata(before)),
    }
    handback = {
        'kind': kind, 'namespace': namespace,
        'name': live.metadata.name, 'uid': live.metadata.uid,
        'resource_version': live.metadata.resource_version,
    }
    return preview, handback


@pytest.mark.parametrize('kind', ['Namespace', 'ResourceQuota'])
def test_verified_historical_profile_residue_is_advisory_only(kind):
    live = resource(kind)
    preview, handback = evidence(live, kind=kind)
    item = inspect_legacy_profile_residue_component(
        preview=preview, handback=handback, live=live,
        profile_public_id='profile-uuid',
    )
    assert item['residual_label'] == 'kaori.io/resource-profile'
    assert item['provider_mutation_performed'] is False
    assert item['provider_spec_preserved'] is True
    assert item['foreign_metadata_preserved'] is True
    assert live.metadata.labels['environment'] == 'uat'
    assert live.spec == (None if kind == 'Namespace' else {
        'hard': {
            'requests.cpu': '2', 'requests.memory': '4Gi',
            'limits.cpu': '4', 'limits.memory': '8Gi',
        },
    })


def test_historical_foreign_metadata_hash_is_not_reinterpreted_by_new_marker_list():
    live = resource()
    old = _stable_sha256(_legacy_retained_metadata(live))
    new = _stable_sha256(_retained_provider_metadata(live))
    assert old != new
    preview, handback = evidence(live)
    assert preview['retained_metadata_sha256'] == old
    assert inspect_legacy_profile_residue_component(
        preview=preview, handback=handback,
        live=live, profile_public_id='profile-uuid',
    )['legacy_foreign_metadata_sha256'] == old


@pytest.mark.parametrize('change', [
    lambda live, preview, handback: live.metadata.labels.update({
        'app.kubernetes.io/managed-by': 'platform-team',
    }),
    lambda live, preview, handback: live.metadata.labels.update({
        'kaori.io/tenant-id': 'tenant-1',
    }),
    lambda live, preview, handback: live.metadata.labels.update({
        'kaori.io/tenant-generation': '1',
    }),
    lambda live, preview, handback: live.metadata.labels.update({
        'kaori.io/profile-id': 'old-profile',
    }),
    lambda live, preview, handback: live.metadata.labels.update({
        'example.org/foreign': 'tampered',
    }),
    lambda live, preview, handback: live.metadata.labels.update({
        'kaori.io/resource-profile': 'other-profile',
    }),
    lambda live, preview, handback: live.metadata.annotations.update({
        'external.io/retained': 'modified',
    }),
    lambda live, preview, handback: setattr(live.metadata, 'uid', 'replaced'),
    lambda live, preview, handback: setattr(live.metadata, 'resource_version', '59'),
    lambda live, preview, handback: setattr(live, 'spec', {'unexpected': 'change'}),
    lambda live, preview, handback: setattr(live.metadata, 'owner_references', [
        {'kind': 'Namespace', 'name': 'foreign'},
    ]),
    lambda live, preview, handback: preview.update({
        'label_keys_to_release': [
            'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
            'kaori.io/resource-profile',
        ],
    }),
    lambda live, preview, handback: preview.update({'dry_run': False}),
    lambda live, preview, handback: handback.update({'uid': 'different'}),
])
def test_assessment_fails_closed_on_provider_or_receipt_drift(change):
    live = resource(kind='ResourceQuota')
    preview, handback = evidence(live, kind='ResourceQuota')
    change(live, preview, handback)
    with pytest.raises(ValueError):
        inspect_legacy_profile_residue_component(
            preview=preview, handback=handback, live=live,
            profile_public_id='profile-uuid',
        )


@pytest.mark.parametrize('values', [
    [],
    [{'kind': 'Namespace', 'name': 'uat-demo', 'uid': 'uid-ns'}] * 2,
    [{'kind': 'Unknown', 'name': 'uat-demo', 'uid': 'uid-ns'}],
    [{'kind': 'Namespace', 'name': 'uat-demo', 'uid': 12}],
    [{'kind': 'Namespace', 'name': 'uat-demo', 'uid': 'uid-ns',
      'namespace': 'other'}],
])
def test_legacy_assessment_scope_rejects_missing_duplicate_or_malformed(values):
    with pytest.raises(ValueError):
        _index_scope(values, title='Test historical receipt')


def test_assessment_has_no_provider_write_or_re_adopt_admission_path():
    from pathlib import Path

    code = (
        Path(__file__).resolve().parents[3]
        / 'app/kubernetes/tenant/native_residual_recovery_assessment.py'
    ).read_text(encoding='utf-8')
    assert 'require_platform_admin_actor(actor_user_id)' in code
    assert 'verify_native_provider_admin_authority(' in code
    assert '_latest_native_dry_run(tenant_id)' in code
    assert 'latest_native_successor_handback(tenant_id)' in code
    assert '_release_dependency_counts(tenant_id)' in code
    assert "provider.get('provider_credential_id')" in code
    assert "'cleanup_authorized': False" in code
    assert "'re_adopt_admitted': False" in code
    assert "'evidence_committed': False" in code
    for forbidden in (
        '.patch_namespace(', '.patch_namespaced_resource_quota(',
        '.patch_namespaced_limit_range(', 'db.session.commit(',
        'db.session.add(', 'release_verified_native_tenant_committed(',
        'adopt_discovered_tenant_committed(', 'handback_native_successor_governance_committed(',
    ):
        assert forbidden not in code

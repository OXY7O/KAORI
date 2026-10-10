"""#1128: source-only safety contracts for governed Native profile residue recovery."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.native_handoff_dry_run import _stable_sha256
from app.kubernetes.tenant.native_residual_recovery_executor import (
    _assert_live_request_actor,
    _unchanged_except_profile,
    build_legacy_profile_residue_patch,
)
from app.kubernetes.tenant.native_residual_recovery_governance import _candidate_digest


def _live(*, uid='uid-uat', rv='1899840', profile='profile-1'):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='tenant-uat-demo', uid=uid, resource_version=rv,
            labels={
                'environment': 'uat',
                'kaori.io/resource-profile': profile,
                'kubernetes.io/metadata.name': 'tenant-uat-demo',
            },
            annotations={'foreign.example/retain': 'value'},
            owner_references=[], finalizers=[], generation=1,
            deletion_timestamp=None, deletion_grace_period_seconds=None,
        ),
        spec=None,
    )


def _component():
    return {
        'kind': 'Namespace', 'namespace': 'tenant-uat-demo',
        'name': 'tenant-uat-demo', 'uid': 'uid-uat',
        'resource_version': '1899840',
        'residual_label': 'kaori.io/resource-profile',
    }


def test_profile_cleanup_uses_exact_uid_rv_and_profile_compare_and_swap():
    source = _live()
    ops = build_legacy_profile_residue_patch(
        component=_component(), resource=source, exact_profile_id='profile-1',
    )
    assert ops == [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'uid-uat'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '1899840'},
        {'op': 'test', 'path': '/metadata/labels/kaori.io~1resource-profile',
         'value': 'profile-1'},
        {'op': 'remove', 'path': '/metadata/labels/kaori.io~1resource-profile'},
    ]
    assert source.metadata.labels['kaori.io/resource-profile'] == 'profile-1'
    assert not any('/spec/' in op['path'] for op in ops)


@pytest.mark.parametrize('change', [
    lambda obj, target: setattr(obj.metadata, 'uid', 'different'),
    lambda obj, target: setattr(obj.metadata, 'resource_version', 'new'),
    lambda obj, target: obj.metadata.labels.update({
        'kaori.io/resource-profile': 'unrelated-profile',
    }),
    lambda obj, target: obj.metadata.labels.update({
        'app.kubernetes.io/managed-by': 'platform-team',
    }),
    lambda obj, target: obj.metadata.labels.update({
        'kaori.io/tenant-id': 'another-tenant',
    }),
    lambda obj, target: target.update({
        'residual_label': 'kaori.io/other-key',
    }),
])
def test_profile_cleanup_patch_rejects_foreign_or_stale_provider_state(change):
    live, target = _live(), _component()
    change(live, target)
    with pytest.raises(ValueError):
        build_legacy_profile_residue_patch(
            component=target, resource=live, exact_profile_id='profile-1',
        )


@pytest.mark.parametrize('tamper', [
    lambda resource: resource.metadata.labels.update({'environment': 'altered'}),
    lambda resource: resource.metadata.labels.update({
        'kaori.io/resource-profile': 'still-there',
    }),
    lambda resource: resource.metadata.annotations.update({
        'foreign.example/retain': 'changed',
    }),
    lambda resource: setattr(resource.metadata, 'finalizers', ['unexpected']),
    lambda resource: setattr(resource, 'spec', {'hard': {'requests.cpu': '99'}}),
    lambda resource: setattr(resource.metadata, 'uid', 'replaced'),
])
def test_cleanup_preview_readback_preserves_nonprofile_metadata_and_spec(tamper):
    before = _live()
    after = deepcopy(before)
    after.metadata.labels.pop('kaori.io/resource-profile')
    assert _unchanged_except_profile(before=before, after=after)
    tamper(after)
    assert not _unchanged_except_profile(before=before, after=after)


def test_shell_cannot_claim_an_arbitrary_admin_identity_for_execution():
    with pytest.raises(ValueError, match='authenticated Platform Admin request'):
        _assert_live_request_actor(1)


def _assessment():
    return {
        'status': 'read_only_recovery_candidate',
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1',
        'generation': 1,
        'release_plan_sha256': 'a' * 64,
        'historical_handback_plan_sha256': 'b' * 64,
        'successor_owner': 'platform-team',
        'components': [_component()],
        'component_count': 1,
        'residual_component_count': 1,
        'provider_identity_verified': True,
        'historical_spec_and_foreign_metadata_verified': True,
        'provider_mutation_performed': False,
        'cleanup_authorized': False,
        're_adopt_admitted': False,
    }


def test_approval_candidate_digest_is_bound_to_exact_provider_identity():
    assessed = _assessment()
    original = _candidate_digest(assessed)
    assessed['components'][0]['resource_version'] = 'changed'
    assert _candidate_digest(assessed) != original


@pytest.mark.parametrize('field,value', [
    ('status', 'verified'),
    ('cleanup_authorized', True),
    ('re_adopt_admitted', True),
    ('provider_identity_verified', False),
    ('provider_mutation_performed', True),
    ('residual_component_count', 0),
])
def test_nonadvisory_assessment_cannot_become_recovery_plan(field, value):
    assessed = _assessment()
    assessed[field] = value
    with pytest.raises(ValueError):
        _candidate_digest(assessed)


def _recovery_fixture():
    release = {
        'tenant_id': 'tenant-1', 'status': 'released',
        'release_mode': 'managed_handoff', 'provider_handoff_verified': True,
        'plan_sha256': 'a' * 64, 'successor_owner': 'platform-team',
    }
    handback = {
        'status': 'verified', 'release_plan_sha256': 'a' * 64,
        'successor_owner': 'platform-team',
        'provider_uid': 'uid-uat', 'resource_version': '1899840',
    }
    receipt = {
        'status': 'verified', 'tenant_id': 'tenant-1',
        'release_plan_sha256': 'a' * 64,
        'handback_plan_sha256': 'b' * 64,
        'successor_owner': 'platform-team',
        'provider_specs_preserved': True,
        'errors': [], 'verified_count': 1, 'expected_component_count': 1,
        'provider_mutation_performed': True,
        're_adopt_admitted': False,
        'verified_components': [{
            'kind': 'Namespace', 'name': 'tenant-uat-demo',
            'namespace': 'tenant-uat-demo', 'uid': 'uid-uat',
            'resource_version': '1899850',
        }],
    }
    receipt['receipt_sha256'] = _stable_sha256(receipt)
    provider_evidence = {
        'handback_governance': handback,
        'residual_recovery_governance': {
            'status': 'verified', 'release_plan_sha256': 'a' * 64,
            'handback_plan_sha256': 'b' * 64,
            'provider_uid': 'uid-uat', 'resource_version': '1899850',
            'receipt_sha256': receipt['receipt_sha256'],
            'provider_metadata_only_verified': True,
        },
    }
    return release, provider_evidence, receipt


def test_new_rv_re_adopt_requires_matching_append_only_verified_recovery(monkeypatch):
    from app.kubernetes.tenant.discovery_adoption import (
        _require_re_adoption_handback_for_managed_release as guard,
    )
    from app.kubernetes.tenant import native_residual_recovery_governance as source

    release, evidence, receipt = _recovery_fixture()
    monkeypatch.setattr(source, 'latest_native_residual_cleanup_execution',
                        lambda tenant_id: receipt)
    guard(
        provider_evidence=evidence, release_evidence=release,
        provider_uid='uid-uat', resource_version='1899850',
    )
    wrong = deepcopy(receipt)
    wrong['verified_components'][0]['uid'] = 'different'
    monkeypatch.setattr(source, 'latest_native_residual_cleanup_execution',
                        lambda tenant_id: wrong)
    with pytest.raises(ValueError):
        guard(
            provider_evidence=evidence, release_evidence=release,
            provider_uid='uid-uat', resource_version='1899850',
        )


@pytest.mark.parametrize('change', [
    lambda r, e: r.update({'status': 'partial_recovery_required'}),
    lambda r, e: r.update({'provider_specs_preserved': False}),
    lambda r, e: r.update({'errors': ['unexpected']}),
    lambda r, e: r.update({'provider_mutation_performed': False}),
    lambda r, e: e['residual_recovery_governance'].update({
        'release_plan_sha256': 'c' * 64,
    }),
    lambda r, e: e['residual_recovery_governance'].update({
        'resource_version': 'wrong',
    }),
])
def test_unverified_or_tampered_recovery_cannot_authorize_new_generation(
    monkeypatch, change,
):
    from app.kubernetes.tenant.discovery_adoption import (
        _require_re_adoption_handback_for_managed_release as guard,
    )
    from app.kubernetes.tenant import native_residual_recovery_governance as source

    release, evidence, receipt = _recovery_fixture()
    change(receipt, evidence)
    monkeypatch.setattr(source, 'latest_native_residual_cleanup_execution',
                        lambda tenant_id: receipt)
    with pytest.raises(ValueError):
        guard(
            provider_evidence=evidence, release_evidence=release,
            provider_uid='uid-uat', resource_version='1899850',
        )


def test_source_only_executor_is_unexposed_to_routes():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    routes = (root / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
    assert 'execute_native_residual_cleanup_committed(' not in routes
    assert 'prepare_native_residual_cleanup_committed(' not in routes
    assert 'approve_native_residual_cleanup_committed(' not in routes

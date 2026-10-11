"""#1229 Capsule read-back and crash/partial recovery must be non-retryable."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_handoff_recovery import (
    capture_capsule_namespace_baseline,
    classify_capsule_namespace_handoff,
    summarize_capsule_recovery,
)


def _namespace(*, name='dev', uid='ns-uid', version='12'):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=name, uid=uid, resource_version=version,
            labels={
                'app.kubernetes.io/managed-by': 'kaori',
                'kaori.io/tenant-id': 'tenant-1',
                'capsule.clastix.io/tenant': 'demo',
                'foreign.example/retained': 'yes',
            },
            annotations={'foreign.example/retained': 'yes'},
            owner_references=[{'kind': 'Tenant', 'name': 'demo'}],
            finalizers=['capsule.clastix.io/namespace-protection'],
            generation=1, deletion_timestamp=None,
            deletion_grace_period_seconds=None,
        ),
        spec={'quota': 'unmodified'},
    )


def _component():
    return {
        'namespace': 'dev', 'kind': 'Namespace', 'name': 'dev',
        'uid': 'ns-uid', 'resource_version': '12', 'authority': 'capsule',
        'handoff': 'external_acceptance_required',
        'ownership': 'kaori_marker_correlated',
    }


def _baseline():
    return capture_capsule_namespace_baseline(
        _component(), _namespace(), tenant_id='tenant-1',
        capsule_tenant_name='demo',
    )


def _transferred():
    obj = _namespace(version='13')
    obj.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
    del obj.metadata.labels['kaori.io/tenant-id']
    return obj


def test_baseline_retains_only_provider_digests_not_raw_spec_or_foreign_values():
    baseline = _baseline()
    assert baseline['dry_run'] is True
    assert baseline['live_provider_unchanged'] is True
    assert baseline['operation'] == 'capsule_metadata_only_json_patch_dry_run'
    assert len(baseline['preserved']['spec_sha256']) == 64
    assert 'quota' not in str(baseline)
    assert 'foreign.example' not in str(baseline)


def test_authoritative_readback_classifies_pending_and_transferred():
    baseline = _baseline()
    pending = classify_capsule_namespace_handoff(
        baseline=baseline, current=_namespace(), tenant_id='tenant-1',
        successor_owner='platform-team',
    )
    moved = classify_capsule_namespace_handoff(
        baseline=baseline, current=_transferred(), tenant_id='tenant-1',
        successor_owner='platform-team',
    )
    assert pending['state'] == 'pending_provider_transfer'
    assert moved['state'] == 'provider_markers_transferred'


@pytest.mark.parametrize('mutation', [
    lambda obj: setattr(obj.metadata, 'uid', 'new-uid'),
    lambda obj: setattr(obj, 'spec', {'quota': 'changed'}),
    lambda obj: obj.metadata.annotations.update({'foreign.example/retained': 'no'}),
    lambda obj: obj.metadata.labels.update({'foreign.example/retained': 'no'}),
    lambda obj: setattr(obj.metadata, 'finalizers', []),
    lambda obj: obj.metadata.labels.update({'app.kubernetes.io/managed-by': 'other'}),
    lambda obj: obj.metadata.labels.update({'kaori.io/new-control': 'unknown'}),
    lambda obj: obj.metadata.labels.update({'capsule.clastix.io/tenant': 'someone-else'}),
])
def test_recovery_fails_closed_on_identity_spec_metadata_or_claim_drift(mutation):
    obj = _transferred()
    mutation(obj)
    with pytest.raises(ValueError):
        classify_capsule_namespace_handoff(
            baseline=_baseline(), current=obj, tenant_id='tenant-1',
            successor_owner='platform-team',
        )


def test_never_silently_retry_a_partial_or_fully_transferred_scope():
    baseline = _baseline()
    second = deepcopy(baseline)
    second.update({'name': 'prod', 'namespace': 'prod', 'uid': 'prod-uid'})
    prod = _namespace(name='prod', uid='prod-uid')
    prod.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
    del prod.metadata.labels['kaori.io/tenant-id']
    prod.metadata.resource_version = '13'
    # An independent exact baseline for prod is needed; no copied baseline digests.
    result = summarize_capsule_recovery(
        baselines=[baseline, second],
        live_namespaces={
            ('dev', 'ns-uid'): _transferred(),
            ('prod', 'prod-uid'): prod,
        },
        tenant_id='tenant-1', successor_owner='platform-team',
    )
    assert result['status'] == 'provider_markers_transferred_consent_unverified'
    assert result['resume_authorized'] is False
    assert result['release_authorized'] is False
    assert result['provider_handoff_verified'] is False
    assert result['auto_retry_authorized'] is False


def test_partial_recovery_status_does_not_grant_resume_or_release():
    baseline = _baseline()
    second = deepcopy(baseline)
    second.update({'name': 'prod', 'namespace': 'prod', 'uid': 'prod-uid'})
    result = summarize_capsule_recovery(
        baselines=[baseline, second],
        live_namespaces={
            ('dev', 'ns-uid'): _transferred(),
            ('prod', 'prod-uid'): _namespace(name='prod', uid='prod-uid'),
        },
        tenant_id='tenant-1', successor_owner='platform-team',
    )
    assert result['status'] == 'partial_handoff_recovery_required'
    assert result['transferred_count'] == 1
    assert result['pending_count'] == 1
    assert result['resume_authorized'] is False
    assert result['release_authorized'] is False


def test_recovery_rejects_missing_extra_or_duplicated_provider_objects():
    baseline = _baseline()
    with pytest.raises(ValueError):
        summarize_capsule_recovery(
            baselines=[baseline], live_namespaces={}, tenant_id='tenant-1',
            successor_owner='platform-team',
        )
    with pytest.raises(ValueError):
        summarize_capsule_recovery(
            baselines=[baseline, deepcopy(baseline)],
            live_namespaces={('dev', 'ns-uid'): _namespace()},
            tenant_id='tenant-1', successor_owner='platform-team',
        )

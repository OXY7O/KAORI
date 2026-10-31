"""Remediation presentation cannot cross Tenant, provider, or evidence generations."""

from copy import deepcopy

import pytest

from app.kubernetes.tenant.access_service import _remediation_matches_access_observation


def evidence_case(provider: str) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    observation: dict[str, object] = {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'observed_at': '2026-10-26T02:00:00+00:00',
        'provider_uid': 'capsule-uid-1',
        'resource_version': '12',
        'evidence_sha256': 'native-digest-1',
    }
    drift: dict[str, object] = {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'evaluated_at': '2026-10-26T02:05:00+00:00',
        'observation_checked_at': '2026-10-26T02:00:00+00:00',
        'source_observed_at': '2026-10-26T02:00:00+00:00',
        'observation_uid': 'capsule-uid-1',
        'observation_resource_version': '12',
        'source_evidence_sha256': 'native-digest-1',
    }
    plan: dict[str, object] = {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'provider': 'capsule' if provider == 'capsule' else 'native_kubernetes',
        'source_target_type': (
            'kubernetes_tenant_access_drift_evidence'
            if provider == 'capsule'
            else 'kubernetes_tenant_native_access_drift_evidence'
        ),
        'source_drift_evaluated_at': '2026-10-26T02:05:00+00:00',
        'auto_mutation_performed': False,
    }
    return observation, drift, plan


@pytest.mark.parametrize('provider', ['capsule', 'native'])
def test_matching_committed_remediation_is_presentable(provider: str) -> None:
    observation, drift, plan = evidence_case(provider)
    assert _remediation_matches_access_observation(provider=provider, observation=observation, drift=drift, plan=plan)


@pytest.mark.parametrize('provider', ['capsule', 'native'])
@pytest.mark.parametrize(
    ('section', 'field', 'changed'),
    [
        ('plan', 'tenant_id', 'tenant-other'),
        ('plan', 'cluster_id', 'cluster-other'),
        ('plan', 'provider', 'wrong-provider'),
        ('plan', 'source_target_type', 'wrong-drift-target'),
        ('plan', 'source_drift_evaluated_at', '2026-10-26T02:07:00+00:00'),
        ('plan', 'auto_mutation_performed', True),
        ('observation', 'tenant_id', 'tenant-other'),
        ('observation', 'observed_at', '2026-10-26T02:04:00+00:00'),
        ('drift', 'evaluated_at', '2026-10-26T02:08:00+00:00'),
        ('drift', 'cluster_id', 'cluster-other'),
    ],
)
def test_unrelated_or_stale_evidence_is_not_presented(provider: str, section: str, field: str, changed: object) -> None:
    observation, drift, plan = evidence_case(provider)
    sources = {'observation': observation, 'drift': drift, 'plan': plan}
    sources[section][field] = changed
    assert not _remediation_matches_access_observation(
        provider=provider, observation=observation, drift=drift, plan=plan
    )


@pytest.mark.parametrize(
    ('provider', 'observation_field', 'drift_field'),
    [
        ('capsule', 'provider_uid', 'observation_uid'),
        ('capsule', 'resource_version', 'observation_resource_version'),
        ('native', 'evidence_sha256', 'source_evidence_sha256'),
    ],
)
def test_provider_fingerprint_mismatch_is_not_presented(
    provider: str, observation_field: str, drift_field: str
) -> None:
    observation, drift, plan = evidence_case(provider)
    altered_drift = deepcopy(drift)
    altered_drift[drift_field] = 'different-provider-snapshot'
    assert observation[observation_field] != altered_drift[drift_field]
    assert not _remediation_matches_access_observation(
        provider=provider, observation=observation, drift=altered_drift, plan=plan
    )


def test_capsule_fallback_observation_timestamp_is_accepted() -> None:
    observation, drift, plan = evidence_case('capsule')
    drift.pop('source_observed_at')
    assert _remediation_matches_access_observation(provider='capsule', observation=observation, drift=drift, plan=plan)

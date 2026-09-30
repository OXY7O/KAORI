from types import SimpleNamespace

from app.kubernetes.tenant.allocation_drift import (
    allocation_differences,
    build_allocation_drift_action_state,
)


def _record(*, drift=None, provider_key='native_kubernetes', authority='native_kubernetes'):
    tenant = SimpleNamespace(
        id='tenant-api',
        provider_key=provider_key,
        reconciliation_authority=authority,
    )
    profile = SimpleNamespace(
        public_id='profile-standard',
        version=1,
        quota_hard_json={},
        limit_defaults_json={},
    )
    return SimpleNamespace(
        id=7,
        namespace='api-prod',
        environment=SimpleNamespace(tenant=tenant),
        resource_profile=profile,
        resource_profile_version=1,
        allocation_quota_json={
            'requests.cpu': '2',
            'limits.cpu': '4',
            'requests.memory': '4Gi',
            'limits.memory': '8Gi',
            'pods': '10',
        },
        allocation_limit_defaults_json={
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
            'default': {'cpu': '500m', 'memory': '512Mi'},
        },
        provisioning_evidence_json={
            'allocation_control_state': 'kaori_managed',
            'allocation': {'provenance': 'kaori_managed'},
            **({'allocation_drift': drift} if drift is not None else {}),
        },
        ownership_status='adopted',
    )


def test_allocation_diff_is_dimension_level_and_quantity_aware():
    record = _record()
    observation = {
        'quota': {
            'requests.cpu': '2000m',
            'limits.cpu': '6',
            'requests.memory': '4096Mi',
            'limits.memory': '12Gi',
            'pods': '20',
        },
        'limits': {
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
            'default': {'cpu': '500m', 'memory': '1Gi'},
        },
    }

    differences = allocation_differences(record, observation)
    by_dimension = {item['dimension']: item for item in differences}

    assert 'requests.cpu' not in by_dimension
    assert 'requests.memory' not in by_dimension
    assert by_dimension['limits.cpu']['kaori_value'] == '4'
    assert by_dimension['limits.cpu']['provider_value'] == '6'
    assert by_dimension['limits.memory']['provider_value'] == '12Gi'
    assert by_dimension['pods']['provider_value'] == '20'
    assert by_dimension['default.memory']['provider_value'] == '1Gi'


def test_bidirectional_actions_are_available_for_native_managed_allocation_drift():
    drift = {
        'blocked_reasons': [],
        'observed': {
            'effective_hash': 'provider-hash',
            'quota': {'requests.cpu': '3'},
            'limits': {},
        },
        'differences': [
            {
                'dimension': 'requests.cpu',
                'kaori_value': '2',
                'provider_value': '3',
            }
        ],
    }
    record = _record(drift=drift)

    state = build_allocation_drift_action_state(record)

    assert record.ownership_status == 'adopted'
    assert state['is_allocation_drift'] is True
    assert state['reapply_supported'] is True
    assert state['accept_supported'] is True


def test_bidirectional_actions_fail_closed_when_provider_ownership_is_ambiguous():
    drift = {
        'blocked_reasons': [
            'ResourceQuota/api-quota no longer carries KAORI allocation ownership metadata.'
        ],
        'observed': {'effective_hash': 'provider-hash'},
        'differences': [],
    }
    record = _record(drift=drift)

    state = build_allocation_drift_action_state(record)

    assert state['reapply_supported'] is False
    assert state['accept_supported'] is False
    assert 'allocation ownership metadata' in state['blocked_reason']


def test_capsule_allocation_drift_stays_control_unavailable_without_admitted_adapter():
    drift = {
        'blocked_reasons': [],
        'observed': {'effective_hash': 'provider-hash'},
        'differences': [],
    }
    record = _record(
        drift=drift,
        provider_key='capsule',
        authority='capsule',
    )

    state = build_allocation_drift_action_state(record)

    assert state['reapply_supported'] is False
    assert state['accept_supported'] is False
    assert 'No admitted reconciliation adapter' in state['blocked_reason']

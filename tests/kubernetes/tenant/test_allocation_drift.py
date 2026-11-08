from types import SimpleNamespace

import app.kubernetes.tenant.allocation_drift as allocation_drift
from app.kubernetes.tenant.allocation_drift import (
    accept_provider_allocation_state,
    allocation_differences,
    apply_provider_mirrored_policy_observation,
    build_allocation_drift_action_state,
    reapply_kaori_allocation_intent,
)


def _record(
    *,
    drift=None,
    provider_key='native_kubernetes',
    authority='native_kubernetes',
    control_state='kaori_managed',
):
    tenant = SimpleNamespace(
        id='tenant-api',
        provider_key=provider_key,
        reconciliation_authority=authority,
        lifecycle_status='ready',
    )
    profile = SimpleNamespace(
        public_id='profile-standard',
        version=1,
        profile_class='custom',
        description='Explicit governance-cutover profile materialized from the adopted provider baseline.',
        quota_hard_json={},
        limit_defaults_json={},
        storage_policy_json={},
    )
    return SimpleNamespace(
        id=7,
        cluster_id='cluster-a',
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
        allocation_storage_policy_json={'min': '1Gi', 'max': '10Gi'},
        provisioning_status='drifted',
        allocation_customized=False,
        capacity_decision_id=None,
        effective_hash='kaori-hash',
        desired_hash='kaori-hash',
        provisioning_message='Allocation drift requires review.',
        provisioning_evidence_json={
            'allocation_control_state': control_state,
            'allocation': {'provenance': control_state},
            **({'allocation_drift': drift} if drift is not None else {}),
        },
        ownership_status='managed' if provider_key == 'native_kubernetes' else 'adopted',
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
        'storage_policy': {'min': '1Gi', 'max': '10Gi'},
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

    assert record.ownership_status == 'managed'
    assert state['is_allocation_drift'] is True
    assert state['reapply_supported'] is True
    assert state['accept_supported'] is True


def test_bidirectional_actions_fail_closed_when_provider_ownership_is_ambiguous():
    drift = {
        'blocked_reasons': ['ResourceQuota/api-quota no longer carries KAORI allocation ownership metadata.'],
        'observed': {'effective_hash': 'provider-hash'},
        'differences': [],
    }
    record = _record(drift=drift)

    state = build_allocation_drift_action_state(record)

    assert state['reapply_supported'] is False
    assert state['accept_supported'] is False
    assert 'allocation ownership metadata' in state['blocked_reason']


def test_capsule_tenant_quota_drift_stays_outside_namespaced_policy_adapter():
    drift = {
        'blocked_reasons': [],
        'observed': {'effective_hash': 'provider-hash'},
        'differences': [],
    }
    record = _record(
        drift=drift,
        provider_key='capsule',
        authority='capsule',
        control_state='kaori_managed',
    )

    state = build_allocation_drift_action_state(record)

    assert state['reapply_supported'] is False
    assert state['accept_supported'] is False
    assert 'No admitted reconciliation adapter' in state['blocked_reason']


def test_reapply_capacity_preflight_uses_live_provider_allocation_as_current(monkeypatch):
    drift = {
        'blocked_reasons': [],
        'observed': {
            'effective_hash': 'provider-hash',
            'quota': {'requests.cpu': '1'},
            'limits': {},
        },
        'differences': [
            {
                'dimension': 'requests.cpu',
                'kaori_value': '2',
                'provider_value': '1',
            }
        ],
    }
    record = _record(drift=drift)
    live = {
        'control_state': 'observed',
        'effective_hash': 'provider-hash',
        'quota': {'requests.cpu': '1'},
        'limits': {},
        'storage_policy': {'min': '1Gi', 'max': '10Gi'},
        'source_resources': [],
    }
    captured = {}

    monkeypatch.setattr(
        allocation_drift,
        '_live_observation_for_action',
        lambda current_record, current_drift: live,
    )

    def fake_capacity_preflight(*, record, profile, current_quota_hard, proposed_quota_hard):
        captured['current'] = dict(current_quota_hard)
        captured['proposed'] = dict(proposed_quota_hard)
        return SimpleNamespace(id=88)

    def fake_reconcile(current_record, **kwargs):
        captured['reconcile'] = kwargs
        return current_record

    monkeypatch.setattr(
        allocation_drift,
        'enforce_observed_namespace_allocation_preflight',
        fake_capacity_preflight,
    )
    monkeypatch.setattr(
        allocation_drift,
        'reconcile_adopted_native_allocation',
        fake_reconcile,
    )

    reapply_kaori_allocation_intent(record)

    assert captured['current'] == {'requests.cpu': '1'}
    assert captured['proposed']['requests.cpu'] == '2'
    assert captured['reconcile']['capacity_decision_id'] == 88
    assert captured['reconcile']['storage_policy'] == {'min': '1Gi', 'max': '10Gi'}
    assert captured['reconcile']['expected_observed_hash'] == 'provider-hash'
    assert captured['reconcile']['failure_status'] == 'drifted'


def test_allocation_reconciliation_is_blocked_outside_committed_drift_state():
    drift = {
        'blocked_reasons': [],
        'observed': {'effective_hash': 'provider-hash'},
        'differences': [],
    }
    record = _record(drift=drift)
    record.provisioning_status = 'ready'

    state = build_allocation_drift_action_state(record)

    assert state['reapply_supported'] is False
    assert state['accept_supported'] is False
    assert 'committed Drifted Namespace state' in state['blocked_reason']


def test_allocation_reconciliation_is_blocked_during_tenant_teardown():
    drift = {
        'blocked_reasons': [],
        'observed': {'effective_hash': 'provider-hash'},
        'differences': [],
    }
    record = _record(drift=drift)
    record.environment.tenant.lifecycle_status = 'decommissioning'

    state = build_allocation_drift_action_state(record)

    assert state['reapply_supported'] is False
    assert state['accept_supported'] is False
    assert 'unavailable during teardown' in state['blocked_reason']


def test_accept_provider_state_commits_live_allocation_without_provider_write(monkeypatch):
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
    live = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'provider-hash',
        'quota': {'requests.cpu': '3'},
        'limits': {},
        'storage_policy': {'min': '2Gi', 'max': '20Gi'},
        'source_resources': [
            {
                'kind': 'ResourceQuota',
                'name': 'kaori-tenant-quota',
                'uid': 'quota-uid',
                'resource_version': '44',
                'managed_by': 'kaori',
                'tenant_id': 'tenant-api',
            }
        ],
    }
    captured = {}

    monkeypatch.setattr(
        allocation_drift,
        '_live_observation_for_action',
        lambda current_record, current_drift: live,
    )

    def fake_capacity_preflight(*, record, profile, current_quota_hard, proposed_quota_hard):
        captured['current'] = dict(current_quota_hard)
        captured['proposed'] = dict(proposed_quota_hard)
        return SimpleNamespace(id=91)

    monkeypatch.setattr(
        allocation_drift,
        'enforce_observed_namespace_allocation_preflight',
        fake_capacity_preflight,
    )

    accept_provider_allocation_state(record)

    assert record.ownership_status == 'managed'
    assert captured['current']['requests.cpu'] == '2'
    assert captured['proposed']['requests.cpu'] == '3'
    assert record.allocation_quota_json == {'requests.cpu': '3'}
    assert record.allocation_storage_policy_json == {'min': '2Gi', 'max': '20Gi'}
    assert record.desired_hash == 'provider-hash'
    assert record.effective_hash == 'provider-hash'
    assert record.provisioning_status == 'ready'
    assert record.capacity_decision_id == 91
    assert record.provisioning_evidence_json['provider_mutation_performed'] is False
    assert record.provisioning_evidence_json['allocation']['provenance'] == 'accepted_provider_state'
    assert 'allocation_drift' not in record.provisioning_evidence_json


def test_pvc_storage_policy_drift_is_dimension_level_and_bidirectional() -> None:
    record = _record()
    observation = {
        'quota': dict(record.allocation_quota_json),
        'limits': dict(record.allocation_limit_defaults_json),
        'storage_policy': {'min': '2Gi', 'max': '20Gi'},
    }

    differences = allocation_differences(record, observation)
    by_dimension = {item['dimension']: item for item in differences}

    assert by_dimension == {
        'pvc.max.storage': {
            'dimension': 'pvc.max.storage',
            'kaori_value': '10Gi',
            'provider_value': '20Gi',
        },
        'pvc.min.storage': {
            'dimension': 'pvc.min.storage',
            'kaori_value': '1Gi',
            'provider_value': '2Gi',
        },
    }


def test_capsule_provider_mirrored_pvc_policy_updates_committed_profile_without_drift(monkeypatch) -> None:
    record = _record(
        provider_key='capsule',
        authority='capsule',
        control_state='provider_mirrored_policy',
    )
    record.allocation_quota_json = {}
    record.allocation_limit_defaults_json = {}
    record.allocation_storage_policy_json = {'min': '1Gi', 'max': '10Gi'}
    record.resource_profile.description = (
        'Provider-equivalent namespaced Container/PVC policy imported during Capsule adoption.'
    )
    record.resource_profile.limit_defaults_json = {}
    record.resource_profile.storage_policy_json = {'min': '1Gi', 'max': '10Gi'}
    record.resource_profile.version = 1
    record.provisioning_evidence_json = {
        'allocation_control_state': 'provider_mirrored_policy',
        'provider_policy_mirror': {
            'authority': 'capsule',
            'source': 'capsule_generated_namespace_policy',
        },
    }

    fake_query = SimpleNamespace(
        filter=lambda *args, **kwargs: SimpleNamespace(order_by=lambda *order: SimpleNamespace(all=lambda: [record]))
    )
    tenant_namespace_model = allocation_drift.TenantNamespace
    monkeypatch.setattr(
        allocation_drift,
        'TenantNamespace',
        SimpleNamespace(
            query=fake_query,
            provisioning_status=tenant_namespace_model.provisioning_status,
            cluster_id=tenant_namespace_model.cluster_id,
            id=tenant_namespace_model.id,
        ),
    )

    fake_cluster = SimpleNamespace(id='cluster-a')
    monkeypatch.setattr(
        allocation_drift.db.session,
        'get',
        lambda model, key: fake_cluster,
    )
    monkeypatch.setattr(
        allocation_drift.runtime_adapter,
        'build_client',
        lambda cluster: SimpleNamespace(core_api=lambda: object()),
    )
    monkeypatch.setattr(
        allocation_drift,
        'observe_native_namespace_allocation',
        lambda api, namespace: {
            'control_state': 'observed',
            'effective_hash': 'provider-policy-hash',
            'quota': {'requests.cpu': '99'},
            'limits': {'default_request': {'cpu': '250m'}},
            'storage_policy': {'min': '2Gi', 'max': '20Gi'},
            'unsupported_dimensions': [],
            'ambiguous_dimensions': [],
            'source_resources': [
                {
                    'kind': 'LimitRange',
                    'name': 'capsule-generated',
                }
            ],
        },
    )
    monkeypatch.setattr(allocation_drift.db.session, 'flush', lambda: None)

    result = apply_provider_mirrored_policy_observation()

    assert result['mirrored_namespace_ids'] == [7]
    assert result['updated_namespace_ids'] == [7]
    assert result['provider_mutation_performed'] is False
    assert record.provisioning_status == 'ready'
    assert record.allocation_quota_json == {}
    assert record.allocation_limit_defaults_json == {'default_request': {'cpu': '250m'}}
    assert record.allocation_storage_policy_json == {'min': '2Gi', 'max': '20Gi'}
    assert record.resource_profile.limit_defaults_json == {'default_request': {'cpu': '250m'}}
    assert record.resource_profile.storage_policy_json == {'min': '2Gi', 'max': '20Gi'}
    assert record.resource_profile.version == 2
    assert record.resource_profile_version == 2
    assert record.provisioning_evidence_json['allocation_control_state'] == 'provider_mirrored_policy'
    assert record.provisioning_evidence_json['provider_policy_mirror']['provider_values_changed'] is True
    assert 'allocation_drift' not in record.provisioning_evidence_json

from types import SimpleNamespace

import pytest

import app.kubernetes.tenant.allocation_cutover as allocation_cutover
from app.kubernetes.tenant.allocation_cutover import (
    allocation_control_state,
    build_allocation_cutover_state,
    reconcile_adopted_native_allocation,
)


def _record(
    *,
    provider_key='native_kubernetes',
    allocation_control_state_value=None,
    allocation_state='observed',
    source_resources=None,
    allocation_authority='native_namespaced',
):
    tenant = SimpleNamespace(
        provider_key=provider_key,
        reconciliation_authority='capsule' if provider_key == 'capsule' else 'native_kubernetes',
        provider_evidence_json={
            'allocation_baseline': {
                'allocation_authority': allocation_authority,
            }
        },
    )
    evidence = {
        'allocation': {
            'provenance': 'adopted_observed',
            'control_state': allocation_state,
            'control_reason': 'Observed allocation remains read-only.',
            'source_resources': source_resources or [],
        }
    }
    if allocation_control_state_value is not None:
        evidence['allocation_control_state'] = allocation_control_state_value
    return SimpleNamespace(
        environment=SimpleNamespace(tenant=tenant),
        ownership_status='adopted',
        provisioning_evidence_json=evidence,
    )


def test_native_adopted_baseline_is_eligible_with_single_authoritative_sources():
    record = _record(
        source_resources=[
            {'kind': 'ResourceQuota', 'name': 'legacy-quota', 'uid': 'rq-1', 'resource_version': '7'},
            {'kind': 'LimitRange', 'name': 'legacy-limits', 'uid': 'lr-1', 'resource_version': '8'},
        ]
    )

    state = build_allocation_cutover_state(record)

    assert allocation_control_state(record) == 'adopted_observed'
    assert state['supported'] is True
    assert state['state'] == 'adopted_observed'
    assert state['authority'] == 'native_kubernetes'


def test_native_cutover_fails_closed_when_multiple_quota_sources_remain():
    record = _record(
        source_resources=[
            {'kind': 'ResourceQuota', 'name': 'quota-a'},
            {'kind': 'ResourceQuota', 'name': 'quota-b'},
        ]
    )

    state = build_allocation_cutover_state(record)

    assert state['supported'] is False
    assert state['state'] == 'control_unavailable'
    assert 'at most one authoritative ResourceQuota' in state['reason']


def test_capsule_cutover_does_not_bypass_capsule_authority_with_native_write():
    record = _record(
        provider_key='capsule',
        allocation_authority='capsule_tenant_resource_quotas',
        source_resources=[{'kind': 'ResourceQuota', 'name': 'capsule-api-0'}],
    )

    state = build_allocation_cutover_state(record)

    assert state['supported'] is False
    assert state['state'] == 'control_unavailable'
    assert state['authority'] == 'capsule_tenant_resource_quotas'
    assert 'will not bypass Capsule' in state['reason']


def test_successful_control_state_is_separate_from_namespace_ownership():
    record = _record(allocation_control_state_value='kaori_managed')

    state = build_allocation_cutover_state(record)

    assert record.ownership_status == 'managed'
    assert allocation_control_state(record) == 'kaori_managed'
    assert state['supported'] is False
    assert state['state'] == 'kaori_managed'



class _FakeCoreApi:
    def __init__(self):
        self.created_quotas = []
        self.created_limit_ranges = []
        self.patched_namespaces = []

    def read_namespace(self, name):
        labels = self.patched_namespaces[-1][1]['metadata']['labels'] if self.patched_namespaces else {}
        return SimpleNamespace(
            metadata=SimpleNamespace(
                labels=labels,
                resource_version='1',
            )
        )

    def patch_namespace(self, name, body):
        self.patched_namespaces.append((name, body))

    def read_namespaced_resource_quota(self, name, namespace):
        return None

    def read_namespaced_limit_range(self, name, namespace):
        return None

    def create_namespaced_resource_quota(self, namespace, body):
        self.created_quotas.append((namespace, body))

    def create_namespaced_limit_range(self, namespace, body):
        self.created_limit_ranges.append((namespace, body))


class _FakeRuntimeClient:
    def __init__(self, api):
        self._api = api

    def core_api(self):
        return self._api


def _reconcile_record():
    tenant = SimpleNamespace(
        id='tenant-1',
        provider_key='native_kubernetes',
        reconciliation_authority='native_kubernetes',
        provider_evidence_json={},
    )
    environment = SimpleNamespace(
        tenant=tenant,
        environment='production',
    )
    return SimpleNamespace(
        id=42,
        environment=environment,
        ownership_status='adopted',
        provisioning_evidence_json={
            'allocation': {
                'provenance': 'adopted_observed',
                'control_state': 'observed',
                'control_reason': 'Observed allocation remains read-only.',
                'source_resources': [],
            }
        },
        cluster_id=7,
        namespace='api-prod',
        effective_hash='before-hash',
        desired_hash=None,
        provisioning_status='ready',
        provisioning_message='Observed allocation baseline.',
        last_reconciled_at=None,
        resource_profile=None,
        resource_profile_id=None,
        resource_profile_version=None,
        allocation_quota_json={},
        allocation_limit_defaults_json={},
        allocation_storage_policy_json={},
        allocation_customized=False,
        capacity_decision_id=None,
    )


def _profile():
    return SimpleNamespace(
        id=9,
        public_id='profile-standard',
    )


def _install_reconcile_fakes(monkeypatch, observations):
    api = _FakeCoreApi()
    monkeypatch.setattr(
        allocation_cutover,
        'db',
        SimpleNamespace(session=SimpleNamespace(get=lambda model, object_id: SimpleNamespace(id=object_id))),
    )
    monkeypatch.setattr(
        allocation_cutover.runtime_adapter,
        'build_client',
        lambda cluster: _FakeRuntimeClient(api),
    )
    observed = iter(observations)
    monkeypatch.setattr(
        allocation_cutover,
        'observe_native_namespace_allocation',
        lambda api, namespace: next(observed),
    )
    return api


def test_verified_native_cutover_transfers_namespace_and_allocation_control_to_kaori(monkeypatch):
    record = _reconcile_record()
    before = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'before-hash',
        'quota': {'requests.cpu': '1'},
        'limits': {},
        'storage_policy': {},
        'source_resources': [],
    }
    after = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'after-hash',
        'quota': {'requests.cpu': '2'},
        'limits': {},
        'storage_policy': {},
        'source_resources': [],
    }
    _install_reconcile_fakes(monkeypatch, [before, after])

    reconcile_adopted_native_allocation(
        record,
        profile=_profile(),
        resource_profile_version=1,
        allocation_customized=False,
        capacity_decision_id=123,
        quota_hard={'requests.cpu': '2'},
        limit_defaults={},
        operation='allocation_governance_cutover',
    )

    assert record.ownership_status == 'adopted'
    assert allocation_control_state(record) == 'kaori_managed'
    assert record.desired_hash == 'after-hash'
    assert record.effective_hash == 'after-hash'
    assert record.provisioning_status == 'ready'
    assert record.provisioning_evidence_json['allocation']['provenance'] == 'kaori_managed'
    assert record.provisioning_evidence_json['allocation']['previous_provenance'] == 'adopted_observed'


def test_readback_mismatch_never_marks_failed_cutover_managed(monkeypatch):
    record = _reconcile_record()
    before = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'before-hash',
        'quota': {'requests.cpu': '1'},
        'limits': {},
        'storage_policy': {},
        'source_resources': [],
    }
    mismatched = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'unexpected-hash',
        'quota': {'requests.cpu': '3'},
        'limits': {},
        'storage_policy': {},
        'source_resources': [],
    }
    _install_reconcile_fakes(monkeypatch, [before, mismatched])

    with pytest.raises(ValueError, match='Provider read-back does not match'):
        reconcile_adopted_native_allocation(
            record,
            profile=_profile(),
            resource_profile_version=1,
            allocation_customized=False,
            capacity_decision_id=123,
            quota_hard={'requests.cpu': '2'},
            limit_defaults={},
            operation='allocation_governance_cutover',
        )

    assert record.ownership_status == 'adopted'
    assert allocation_control_state(record) == 'adopted_observed'
    assert record.desired_hash is None
    assert record.effective_hash == 'before-hash'
    assert record.provisioning_status == 'failed'
    failure = record.provisioning_evidence_json['allocation_reconcile_failure']
    assert failure['provider_mutation_may_have_started'] is True
    assert failure['control_state'] == 'adopted_observed'


def test_live_hash_change_blocks_cutover_before_provider_mutation(monkeypatch):
    record = _reconcile_record()
    changed_before = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'changed-out-of-band',
        'quota': {'requests.cpu': '2'},
        'limits': {},
        'storage_policy': {},
        'source_resources': [],
    }
    api = _install_reconcile_fakes(monkeypatch, [changed_before])

    with pytest.raises(ValueError, match='Live provider allocation changed'):
        reconcile_adopted_native_allocation(
            record,
            profile=_profile(),
            resource_profile_version=1,
            allocation_customized=False,
            capacity_decision_id=123,
            quota_hard={'requests.cpu': '2'},
            limit_defaults={},
            operation='allocation_governance_cutover',
        )

    assert api.created_quotas == []
    assert api.created_limit_ranges == []
    assert allocation_control_state(record) == 'adopted_observed'
    assert record.desired_hash is None


def test_native_cutover_writes_and_verifies_pvc_storage_policy(monkeypatch) -> None:
    record = _reconcile_record()
    before = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'before-hash',
        'quota': {'requests.cpu': '2'},
        'limits': {},
        'storage_policy': {'min': '1Gi', 'max': '10Gi'},
        'source_resources': [],
    }
    after = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'after-hash',
        'quota': {'requests.cpu': '2'},
        'limits': {},
        'storage_policy': {'min': '2Gi', 'max': '20Gi'},
        'source_resources': [],
    }
    api = _install_reconcile_fakes(monkeypatch, [before, after])

    reconcile_adopted_native_allocation(
        record,
        profile=_profile(),
        resource_profile_version=1,
        allocation_customized=True,
        capacity_decision_id=124,
        quota_hard={'requests.cpu': '2'},
        limit_defaults={},
        storage_policy={'min': '2Gi', 'max': '20Gi'},
        operation='allocation_governance_cutover',
    )

    assert record.allocation_storage_policy_json == {'min': '2Gi', 'max': '20Gi'}
    assert len(api.created_limit_ranges) == 1
    limit_range = api.created_limit_ranges[0][1]
    pvc_items = [item for item in limit_range.spec.limits if item.type == 'PersistentVolumeClaim']
    assert len(pvc_items) == 1
    assert pvc_items[0].min == {'storage': '2Gi'}
    assert pvc_items[0].max == {'storage': '20Gi'}
    assert record.provisioning_evidence_json['allocation_history'][-1]['to']['storage_policy'] == {
        'min': '2Gi',
        'max': '20Gi',
    }

def test_storage_only_takeover_keeps_limit_range_and_pvc_policy(monkeypatch) -> None:
    record = _reconcile_record()
    before = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'before-hash',
        'quota': {},
        'limits': {},
        'storage_policy': {'min': '1Gi', 'max': '10Gi'},
        'source_resources': [],
    }
    after = {
        'control_state': 'observed',
        'control_reason': '',
        'effective_hash': 'after-hash',
        'quota': {},
        'limits': {},
        'storage_policy': {'min': '1Gi', 'max': '10Gi'},
        'source_resources': [],
    }
    api = _install_reconcile_fakes(monkeypatch, [before, after])

    reconcile_adopted_native_allocation(
        record,
        profile=_profile(),
        resource_profile_version=1,
        allocation_customized=True,
        capacity_decision_id=None,
        quota_hard={},
        limit_defaults={},
        storage_policy={'min': '1Gi', 'max': '10Gi'},
        operation='adoption_takeover',
    )

    assert api.created_quotas == []
    assert len(api.created_limit_ranges) == 1
    pvc_items = [
        item
        for item in api.created_limit_ranges[0][1].spec.limits
        if item.type == 'PersistentVolumeClaim'
    ]
    assert len(pvc_items) == 1
    assert pvc_items[0].min == {'storage': '1Gi'}
    assert pvc_items[0].max == {'storage': '10Gi'}
    assert record.allocation_storage_policy_json == {'min': '1Gi', 'max': '10Gi'}
    assert record.ownership_status == 'managed'
    assert allocation_control_state(record) == 'kaori_managed'


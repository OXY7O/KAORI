from types import SimpleNamespace

from app.kubernetes.tenant.allocation_cutover import (
    allocation_control_state,
    build_allocation_cutover_state,
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

    assert record.ownership_status == 'adopted'
    assert allocation_control_state(record) == 'kaori_managed'
    assert state['supported'] is False
    assert state['state'] == 'kaori_managed'

from types import SimpleNamespace

import app.kubernetes.tenant.capsule_allocation_governance as capsule_allocation
from app.kubernetes.tenant.capsule_allocation_governance import (
    build_capsule_shared_allocation_cutover_state,
)


def _tenant(
    *,
    authority='capsule_global_resource_quota',
    capability='available',
    provider_state='capsule',
    served_version='v1beta2',
    sources=None,
    ambiguous_dimensions=None,
    unsupported_dimensions=None,
):
    return SimpleNamespace(
        id='tenant-api',
        provider_key='capsule',
        reconciliation_authority='capsule',
        provider_state=provider_state,
        lifecycle_status='ready',
        provider_evidence_json={
            'capsule': {
                'capabilities': {
                    'shared_global_quota': capability,
                }
            },
            'allocation_baseline': {
                'allocation_authority': authority,
                'ambiguous_dimensions': ambiguous_dimensions or [],
                'unsupported_dimensions': unsupported_dimensions or [],
                'shared_scope': 'Tenant',
                'global_resource_quota': {
                    'served_version': served_version,
                    'quota': {
                        'limits.cpu': '4',
                        'limits.memory': '8Gi',
                        'pods': '10',
                        'requests.storage': '1Gi',
                    },
                    'source_resources': sources
                    if sources is not None
                    else [
                        {
                            'kind': 'GlobalResourceQuota',
                            'name': 'api-quota',
                            'uid': 'grq-uid',
                            'resource_version': '12',
                        }
                    ],
                },
            },
        },
    )


def _no_existing_intent(monkeypatch):
    monkeypatch.setattr(
        capsule_allocation,
        '_managed_shared_intent',
        lambda tenant: None,
    )


def test_admitted_global_resource_quota_is_eligible_for_capsule_cutover(monkeypatch):
    _no_existing_intent(monkeypatch)
    state = build_capsule_shared_allocation_cutover_state(_tenant())

    assert state['supported'] is True
    assert state['state'] == 'adopted_observed'
    assert state['authority'] == 'capsule_global_resource_quota'
    assert state['source']['name'] == 'api-quota'
    assert state['source']['uid'] == 'grq-uid'
    assert state['source']['resource_version'] == '12'


def test_tenant_spec_resource_quotas_remains_control_unavailable(monkeypatch):
    _no_existing_intent(monkeypatch)
    state = build_capsule_shared_allocation_cutover_state(
        _tenant(authority='capsule_tenant_resource_quotas')
    )

    assert state['supported'] is False
    assert state['state'] == 'control_unavailable'
    assert 'not a single Capsule GlobalResourceQuota' in state['reason']


def test_degraded_shared_global_quota_capability_fails_closed(monkeypatch):
    _no_existing_intent(monkeypatch)
    state = build_capsule_shared_allocation_cutover_state(
        _tenant(capability='degraded')
    )

    assert state['supported'] is False
    assert 'shared_global_quota capability is unavailable or degraded' in state['reason']


def test_multiple_global_resource_quota_sources_fail_closed(monkeypatch):
    _no_existing_intent(monkeypatch)
    state = build_capsule_shared_allocation_cutover_state(
        _tenant(
            sources=[
                {
                    'kind': 'GlobalResourceQuota',
                    'name': 'api-a',
                    'uid': 'a',
                    'resource_version': '1',
                },
                {
                    'kind': 'GlobalResourceQuota',
                    'name': 'api-b',
                    'uid': 'b',
                    'resource_version': '1',
                },
            ]
        )
    )

    assert state['supported'] is False
    assert 'Exactly one authoritative GlobalResourceQuota source is required' in state['reason']


def test_unsupported_capsule_api_version_fails_closed(monkeypatch):
    _no_existing_intent(monkeypatch)
    state = build_capsule_shared_allocation_cutover_state(
        _tenant(served_version='v1beta1')
    )

    assert state['supported'] is False
    assert 'requires served capsule.clastix.io/v1beta2' in state['reason']

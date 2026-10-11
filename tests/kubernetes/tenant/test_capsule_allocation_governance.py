from types import SimpleNamespace

import app.kubernetes.tenant.capsule_allocation_governance as capsule_allocation
from app.kubernetes.tenant.capsule_allocation_governance import (
    _desired_shared_spec,
    _quota_differences,
    build_capsule_shared_allocation_cutover_state,
    build_capsule_shared_drift_action_state,
    observe_managed_capsule_shared_allocation,
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
    monkeypatch.setattr(capsule_allocation, '_active_shared_intents', lambda tenant_id: [])
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
    state = build_capsule_shared_allocation_cutover_state(_tenant(authority='capsule_tenant_resource_quotas'))

    assert state['supported'] is False
    assert state['state'] == 'control_unavailable'
    assert 'not a single Capsule GlobalResourceQuota' in state['reason']


def test_degraded_shared_global_quota_capability_fails_closed(monkeypatch):
    _no_existing_intent(monkeypatch)
    state = build_capsule_shared_allocation_cutover_state(_tenant(capability='degraded'))

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
    state = build_capsule_shared_allocation_cutover_state(_tenant(served_version='v1beta1'))

    assert state['supported'] is False
    assert 'requires served capsule.clastix.io/v1beta2' in state['reason']


def test_existing_advanced_global_quota_intent_blocks_canonical_cutover(monkeypatch):
    generic_intent = SimpleNamespace(
        status='ready',
        reconciliation_evidence_json={},
    )
    monkeypatch.setattr(
        capsule_allocation,
        '_active_shared_intents',
        lambda tenant_id: [generic_intent],
    )
    monkeypatch.setattr(
        capsule_allocation,
        '_managed_shared_intent',
        lambda tenant: None,
    )

    state = build_capsule_shared_allocation_cutover_state(_tenant())

    assert state['supported'] is False
    assert 'advanced intent already owns this Tenant resource path' in state['reason']


def test_shared_spec_cutover_preserves_capsule_namespace_selectors():
    current = {
        'spec': {
            'namespaceSelectors': [
                {
                    'matchLabels': {
                        'capsule.clastix.io/tenant': 'api',
                    }
                }
            ],
            'quota': {
                'hard': {
                    'requests.cpu': '4',
                    'requests.memory': '8Gi',
                }
            },
        }
    }

    desired = _desired_shared_spec(
        current,
        {
            'requests.cpu': '6',
            'requests.memory': '12Gi',
        },
    )

    assert desired['namespaceSelectors'] == current['spec']['namespaceSelectors']
    assert desired['quota']['hard']['requests.cpu'] == '6'
    assert desired['quota']['hard']['requests.memory'] == '12Gi'


def test_capsule_shared_quota_diff_uses_kubernetes_quantity_semantics():
    differences = _quota_differences(
        {
            'requests.cpu': '1',
            'requests.memory': '1024Mi',
        },
        {
            'requests.cpu': '1000m',
            'requests.memory': '1Gi',
        },
    )

    assert differences == []


def test_capsule_shared_reconcile_requires_committed_drift_state():
    tenant = _tenant()
    intent = SimpleNamespace(
        tenant=tenant,
        status='ready',
        reconciliation_evidence_json={
            'allocation_governance_scope': 'tenant_shared',
        },
    )

    state = build_capsule_shared_drift_action_state(intent)

    assert state['reapply_supported'] is False
    assert state['accept_supported'] is False
    assert 'requires committed Drifted state' in state['blocked_reason']


def test_capsule_shared_reconcile_blocks_when_provider_degrades():
    tenant = _tenant(provider_state='capsule_degraded')
    intent = SimpleNamespace(
        tenant=tenant,
        status='drifted',
        reconciliation_evidence_json={
            'allocation_governance_scope': 'tenant_shared',
            'allocation_drift': {
                'differences': [
                    {
                        'dimension': 'requests.cpu',
                        'kaori_value': '4',
                        'provider_value': '6',
                    }
                ],
                'blocked_reasons': [],
            },
        },
    )

    state = build_capsule_shared_drift_action_state(intent)

    assert state['reapply_supported'] is False
    assert state['accept_supported'] is False
    assert 'Capsule provider is degraded or unavailable' in state['blocked_reason']


def test_capsule_shared_observation_blocks_selector_drift(monkeypatch):
    tenant = _tenant()
    intent = SimpleNamespace(
        tenant=tenant,
        desired_spec_json={
            'namespaceSelectors': [
                {
                    'matchLabels': {
                        'capsule.clastix.io/tenant': 'api',
                    }
                }
            ],
            'quota': {
                'hard': {
                    'requests.cpu': '4',
                    'requests.memory': '8Gi',
                }
            },
        },
        reconciliation_evidence_json={
            'allocation_governance_scope': 'tenant_shared',
            'provider_source': {
                'kind': 'GlobalResourceQuota',
                'name': 'api-quota',
                'uid': 'grq-uid',
                'resource_version': '12',
            },
        },
    )
    monkeypatch.setattr(
        capsule_allocation,
        '_live_global_resource_quota',
        lambda tenant, expected_source, require_resource_version_match: (
            {
                'spec': {
                    'namespaceSelectors': [
                        {
                            'matchLabels': {
                                'capsule.clastix.io/tenant': 'other-tenant',
                            }
                        }
                    ],
                    'quota': {
                        'hard': {
                            'requests.cpu': '4',
                            'requests.memory': '8Gi',
                        }
                    },
                }
            },
            {
                'kind': 'GlobalResourceQuota',
                'name': 'api-quota',
                'uid': 'grq-uid',
                'resource_version': '13',
            },
        ),
    )

    observation = observe_managed_capsule_shared_allocation(intent)

    assert observation['differences'] == []
    assert observation['observed_matches_desired'] is False
    assert any('selector or non-quota authority fields changed' in reason for reason in observation['blocked_reasons'])


def test_capsule_tenant_spec_quota_is_not_a_global_quota_error(monkeypatch):
    _no_existing_intent(monkeypatch)
    state = build_capsule_shared_allocation_cutover_state(
        _tenant(authority='capsule_tenant_resource_quotas', sources=[], served_version='')
    )
    assert state['supported'] is False
    assert state['applicable'] is False
    assert state['detected_authority'] == 'Capsule Tenant.spec.resourceQuotas'
    assert state['source_count'] == 0
    assert state['authority'] == 'capsule_tenant_resource_quotas'
    assert 'requires served capsule.clastix.io/v1beta2' not in state['reason']


def test_no_quota_source_is_nonapplicable_not_an_api_version_failure(monkeypatch):
    _no_existing_intent(monkeypatch)
    state = build_capsule_shared_allocation_cutover_state(
        _tenant(authority='none_observed', sources=[], served_version='')
    )
    assert state['supported'] is False
    assert state['applicable'] is False
    assert state['source_count'] == 0
    assert state['detected_authority'] == 'No committed allocation authority'
    assert 'Exactly one authoritative GlobalResourceQuota source is required' in state['reason']
    assert 'requires served capsule.clastix.io/v1beta2' not in state['reason']


def test_declared_grq_without_source_still_blocks_without_false_version_message(monkeypatch):
    _no_existing_intent(monkeypatch)
    state = build_capsule_shared_allocation_cutover_state(
        _tenant(sources=[], served_version='')
    )
    assert state['applicable'] is True
    assert state['supported'] is False
    assert state['source_count'] == 0
    assert 'Exactly one authoritative GlobalResourceQuota source is required' in state['reason']
    assert 'requires served capsule.clastix.io/v1beta2' not in state['reason']


def test_capsule_shared_governance_guidance_is_read_only_and_links_only_admitted_alternative():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    shared = (
        root / 'app/templates/kubernetes/tenant/partials/_capsule_shared_allocation_cutover.html'
    ).read_text(encoding='utf-8')
    quota = (
        root / 'app/templates/kubernetes/tenant/partials/_capsule_tenant_quota_cutover.html'
    ).read_text(encoding='utf-8')
    workspace = (root / 'app/templates/kubernetes/tenant/namespace_provisioning.html').read_text(
        encoding='utf-8'
    )
    assert 'GlobalResourceQuota governance blockers' in shared
    assert 'Other Capsule allocation authorities' in shared
    assert "state.get('applicable') and not state.get('supported')" in shared
    assert "if state.get('authority') == 'capsule_tenant_resource_quotas'" in shared
    assert "elif state.get('authority') == 'none_observed'" in shared
    assert 'href="#capsule-tenant-quota-heading"' in shared
    assert 'id="capsule-tenant-quota-heading"' in quota
    assert 'data-tenant-capsule-allocation-workspace' in workspace
    assert 'No Tenant-level quota authority is recorded.' in shared
    assert 'Not applicable here' in shared
    assert shared.count('data-tenant-shared-allocation-form') == 1
    assert shared.count('type="submit"') == 1
    assert shared.count('name="csrf_token"') == 1


def test_no_tenant_quota_configured_requires_complete_committed_provider_observation(monkeypatch):
    _no_existing_intent(monkeypatch)
    tenant = _tenant(authority='none_observed', sources=[], served_version='v1beta2')
    baseline = tenant.provider_evidence_json['allocation_baseline']
    baseline['tenant_resource_quota'] = None
    state = build_capsule_shared_allocation_cutover_state(tenant)
    assert state['no_tenant_quota_configured'] is True
    assert state['supported'] is False
    assert state['applicable'] is False
    assert state['source_count'] == 0


def test_new_capsule_tenant_without_allocation_sync_does_not_claim_no_quota(monkeypatch):
    _no_existing_intent(monkeypatch)
    tenant = _tenant(authority='none_observed', sources=[], served_version='')
    state = build_capsule_shared_allocation_cutover_state(tenant)
    assert state['no_tenant_quota_configured'] is False  # Missing explicit observation.

    tenant.provider_evidence_json.pop('allocation_baseline')
    state = build_capsule_shared_allocation_cutover_state(tenant)
    assert state['no_tenant_quota_configured'] is False
    assert state['authority'] == 'unknown'
    assert state['supported'] is False


def test_committed_tenant_quota_stays_alternative_authority_not_initial_allocation(monkeypatch):
    _no_existing_intent(monkeypatch)
    tenant = _tenant(authority='capsule_tenant_resource_quotas', sources=[], served_version='')
    baseline = tenant.provider_evidence_json['allocation_baseline']
    baseline['tenant_resource_quota'] = {'scope': 'Tenant', 'quota': {'requests.cpu': '1'}}
    state = build_capsule_shared_allocation_cutover_state(tenant)
    assert state['no_tenant_quota_configured'] is False
    assert state['detected_authority'] == 'Capsule Tenant.spec.resourceQuotas'


def test_capsule_zero_quota_help_is_read_only_in_shared_allocation_ui():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    template = (
        root / 'app/templates/kubernetes/tenant/partials/_capsule_shared_allocation_cutover.html'
    ).read_text(encoding='utf-8')
    assert "state.get('no_tenant_quota_configured')" in template
    assert 'No Tenant Quota Configured' in template
    assert 'this is not a failed deployment' in template
    assert 'Initial quota configuration is a separate governed workflow' in template
    assert 'No Tenant-level quota authority is recorded.' in template
    assert template.count('data-tenant-shared-allocation-form') == 1
    assert template.count('name="csrf_token"') == 1

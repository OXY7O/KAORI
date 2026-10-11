"""#1229 Capsule worklist remains operator-only and bounded (authored, not run)."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.capsule_handoff_resource_admission import assess_capsule_resource_handoff_scope
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint


def _case():
    objects = [
        {
            'kind': 'ResourceQuota', 'namespace': 'demo-dev', 'name': 'quota',
            'uid': 'quota-uid', 'resource_version': '7', 'origin': 'kaori_correlated',
            'policy_sha256': 'e' * 64,
        },
        {
            'kind': 'LimitRange', 'namespace': 'demo-dev', 'name': 'external-limits',
            'uid': 'limits-uid', 'resource_version': '11', 'origin': 'foreign_preserved',
            'policy_sha256': 'f' * 64,
        },
        {
            'kind': 'RoleBinding', 'namespace': 'demo-dev', 'name': 'grant',
            'uid': 'rb-uid', 'resource_version': '23', 'origin': 'ambiguous_kaori',
            'policy_sha256': 'd' * 64,
        },
    ]
    objects.sort(key=lambda x: (x['namespace'], x['kind'], x['name']))
    lists = [
        {'namespace': 'demo-dev', 'kind': kind, 'list_resource_version': 'list-rv', 'count': amount}
        for kind, amount in [('ResourceQuota', 1), ('LimitRange', 1), ('RoleBinding', 1)]
    ]
    related_sha = _digest({'resources': objects, 'lists': lists})
    shared_items = [{
        'kind': 'GlobalResourceQuota', 'name': 'shared',
        'uid': 'global-uid', 'resource_version': '19',
        'scope': 'direct_tenant_selector', 'policy_sha256': 'a' * 64,
    }]
    shared_sha = _digest({
        'api_version': 'v1beta2', 'list_resource_version': 'cluster-rv',
        'resources': shared_items,
    })
    plan = {
        'plan_sha256': 'c' * 64,
        'handoff_components': [
            {
                'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid',
                'resource_version': '2', 'authority': 'capsule',
                'ownership': 'external_or_unattributed',
                'handoff': 'external_acceptance_required',
                'capsule_spec_sha256': 'e' * 64,
                'capsule_related_resources_sha256': related_sha,
                'capsule_shared_quota_sha256': shared_sha,
                'capsule_related_resources_count': '3',
            },
            {
                'kind': 'Namespace', 'name': 'demo-dev', 'namespace': 'demo-dev',
                'uid': 'ns-uid', 'resource_version': '4', 'authority': 'capsule',
                'ownership': 'kaori_marker_correlated',
                'handoff': 'external_acceptance_required',
            },
        ],
    }
    related = {
        'resources': objects, 'resource_count': 3,
        'list_snapshots': lists, 'resource_sha256': related_sha,
        'global_quota': {
            'served_version': 'v1beta2',
            'list_resource_version': 'cluster-rv',
            'count': len(shared_items),
            'scope_sha256': shared_sha,
            'resources': shared_items,
        },
    }
    return plan, related


def test_worklist_preserves_foreign_policy_and_lists_manual_review_items():
    plan, related = _case()
    result = build_capsule_handoff_worklist(plan=plan, related=related)
    decisions = {item['name']: item['decision'] for item in result['items']}
    assert decisions['demo'] == 'provider_cr_preservation_review_required'
    assert decisions['demo-dev'] == 'candidate_kaori_metadata_handoff_review'
    assert decisions['quota'] == 'explicit_kaori_metadata_handoff_review'
    assert decisions['external-limits'] == 'preserve_foreign_provider_control'
    assert decisions['grant'] == 'operator_origin_investigation'
    assert decisions['shared'] == 'preserve_cluster_scoped_quota'
    assert result['manual_review_count'] == 4
    assert result['status'] == 'operator_review_only'
    assert result['provider_execution_admitted'] is False
    assert result['dry_run_admitted'] is False
    assert result['auto_retry_authorized'] is False
    assert result['release_authorized'] is False


@pytest.mark.parametrize('mutation', [
    lambda p, r: p['handoff_components'][1].update(uid=''),
    lambda p, r: r.update(resource_sha256='d' * 64),
    lambda p, r: r['global_quota'].update(scope_sha256='d' * 64),
    lambda p, r: r['resources'][0].update(origin='provider_but_not_proven'),
    lambda p, r: r['resources'].append(deepcopy(r['resources'][0])),
    lambda p, r: r['resources'][0].update(namespace='other-ns'),
    lambda p, r: r['global_quota']['resources'][0].update(scope='unsupported'),
    lambda p, r: r['global_quota']['resources'][0].update(uid=None),
])
def test_worklist_fails_closed_on_changed_provider_scope_or_unknown_state(mutation):
    plan, related = _case()
    mutation(plan, related)
    with pytest.raises((TypeError, ValueError, KeyError)):
        build_capsule_handoff_worklist(plan=plan, related=related)


def test_worklist_tracks_resource_version_and_policy_change():
    plan, related = _case()
    first = build_capsule_handoff_worklist(plan=plan, related=related)
    related['resources'][0]['resource_version'] = '8'
    related['resource_sha256'] = _digest({
        'resources': related['resources'], 'lists': related['list_snapshots'],
    })
    plan['handoff_components'][0]['capsule_related_resources_sha256'] = related['resource_sha256']
    second = build_capsule_handoff_worklist(plan=plan, related=related)
    assert first['inventory_sha256'] != second['inventory_sha256']
    related['resources'][0]['policy_sha256'] = '9' * 64
    related['resource_sha256'] = _digest({
        'resources': related['resources'], 'lists': related['list_snapshots'],
    })
    plan['handoff_components'][0]['capsule_related_resources_sha256'] = related['resource_sha256']
    third = build_capsule_handoff_worklist(plan=plan, related=related)
    assert second['inventory_sha256'] != third['inventory_sha256']


def test_worklist_digest_is_stable_for_resource_order_only():
    plan, related = _case()
    first = build_capsule_handoff_worklist(plan=plan, related=related)
    related['resources'].reverse()
    # Source order changes, but the provider observer emits sorted canonical rows.
    related['resources'].sort(key=lambda x: (x['namespace'], x['kind'], x['name']))
    second = build_capsule_handoff_worklist(plan=plan, related=related)
    assert first['inventory_sha256'] == second['inventory_sha256']


def test_no_secret_or_rbac_subject_material_in_worklist():
    plan, related = _case()
    result = build_capsule_handoff_worklist(plan=plan, related=related)
    assert 'subjects' not in str(result)
    assert 'credential' not in str(result)
    assert len(result['inventory_sha256']) == 64


def _provenance_case():
    plan, related = _case()
    for obj in related['resources']:
        obj['metadata_sha256'] = '9' * 64
    related['resource_sha256'] = _digest({
        'resources': related['resources'], 'lists': related['list_snapshots'],
    })
    plan['handoff_components'][0]['capsule_related_resources_sha256'] = related['resource_sha256']
    plan['handoff_components'][0]['capsule_rbac_lineage_sha256'] = 'b' * 64
    related.update(
        status='read_only_related_inventory', blockers=[],
        rbac_lineage={
            'status': 'contract_correlated_controller_origin_unverified',
            'lineage_sha256': 'b' * 64, 'contract_correlated': False,
            'controller_origin_verified': False,
            'blockers': ['Capsule effective KAORI RoleBinding origin is ambiguous.'],
        },
    )
    related['global_quota'].update(
        status='observed_not_handoff_authorized', blockers=[],
    )
    plan.update(
        tenant_id='tenant-1', cluster_id='cluster-1', generation=1,
        provider='capsule', requested_by=10,
        requested_at=datetime.now(UTC).isoformat(),
        successor_owner='platform-team', change_reference='CHG-1011',
        provider_identity=[
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '2'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid', 'resource_version': '4'},
        ],
    )
    plan['handoff_fingerprint'] = handoff_fingerprint(plan['handoff_components'])
    plan['plan_sha256'] = _plan_hash(plan)
    return plan, related


def test_per_resource_provenance_denies_capsule_quota_limit_rbac_transfer():
    plan, related = _provenance_case()
    report = assess_capsule_resource_handoff_scope(plan=plan, related=related)
    rows = {row['name']: row for row in report['resources']}
    assert report['status'] == 'resource_specific_controller_provenance_unverified'
    assert report['resource_count'] == 6
    assert report['source_candidate_count'] == 2
    assert rows['demo']['inventory_decision'] == 'provider_cr_preservation_review_required'
    assert rows['demo-dev']['provenance_status'] == 'source_correlated_not_controller_attested'
    assert rows['quota']['provenance_status'] == 'source_correlated_not_controller_attested'
    assert rows['quota']['controller_origin_attested'] is False
    assert rows['external-limits']['inventory_decision'] == 'preserve_foreign_provider_control'
    assert rows['grant']['inventory_decision'] == 'operator_origin_investigation'
    assert rows['shared']['inventory_decision'] == 'preserve_cluster_scoped_quota'
    assert all(item['metadata_only_handoff_admitted'] is False for item in rows.values())
    assert all(item['provider_spec_mutation_allowed'] is False for item in rows.values())
    assert report['resource_specific_handoff_admitted'] is False
    assert report['dry_run_admitted'] is False
    assert report['release_authorized'] is False
    assert report['secret_material_persisted'] is False


def test_incorrect_per_kind_list_count_is_rejected_even_with_recomputed_digest():
    plan, related = _case()
    related['list_snapshots'][0]['count'] = 0
    related['resource_sha256'] = _digest({
        'resources': related['resources'], 'lists': related['list_snapshots'],
    })
    plan['handoff_components'][0]['capsule_related_resources_sha256'] = related['resource_sha256']
    with pytest.raises(ValueError, match='digest|count|inconsistent'):
        build_capsule_handoff_worklist(plan=plan, related=related)


def test_external_namespace_handoff_does_not_get_kaori_transfer_candidate():
    plan, related = _case()
    plan['handoff_components'][1]['ownership'] = 'external_or_unattributed'
    report = build_capsule_handoff_worklist(plan=plan, related=related)
    ns = next(row for row in report['items'] if row['kind'] == 'Namespace')
    assert ns['decision'] == 'operator_origin_investigation'
    assert report['provider_execution_admitted'] is False


def test_kaori_role_binding_needs_source_contract_not_only_manager_label():
    plan, related = _provenance_case()
    record = next(row for row in related['resources'] if row['kind'] == 'RoleBinding')
    record['origin'] = 'kaori_correlated'
    record['metadata_sha256'] = 'e' * 64
    related['resource_sha256'] = _digest({
        'resources': related['resources'], 'lists': related['list_snapshots'],
    })
    plan['handoff_components'][0]['capsule_related_resources_sha256'] = related['resource_sha256']
    plan['handoff_fingerprint'] = handoff_fingerprint(plan['handoff_components'])
    plan['plan_sha256'] = _plan_hash(plan)
    report = assess_capsule_resource_handoff_scope(plan=plan, related=related)
    role = next(item for item in report['resources'] if item['kind'] == 'RoleBinding')
    assert 'rbac_intent_effective_binding_not_proven' in role['blockers']
    assert role['controller_origin_attested'] is False
    assert role['metadata_only_handoff_admitted'] is False


def test_resource_admission_refuses_changed_digests_or_controller_claim_overrides():
    plan, related = _provenance_case()
    baseline = assess_capsule_resource_handoff_scope(plan=plan, related=related)
    related['rbac_lineage']['controller_origin_verified'] = True
    with pytest.raises(ValueError):
        assess_capsule_resource_handoff_scope(plan=plan, related=related)
    related['rbac_lineage']['controller_origin_verified'] = False
    changed = assess_capsule_resource_handoff_scope(plan=plan, related=related)
    assert baseline['resource_review_sha256'] == changed['resource_review_sha256']
    assert changed['controller_origin_verified'] is False

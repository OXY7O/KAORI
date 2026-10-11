"""#1229 Capsule worklist remains operator-only and bounded (authored, not run)."""
from __future__ import annotations

from copy import deepcopy

import pytest

from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist


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
    related_sha = 'a' * 64
    shared_sha = 'b' * 64
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
        'resources': objects, 'resource_sha256': related_sha,
        'global_quota': {
            'scope_sha256': shared_sha,
            'resources': [
                {
                    'kind': 'GlobalResourceQuota', 'name': 'shared',
                    'uid': 'global-uid', 'resource_version': '19',
                    'scope': 'direct_tenant_selector', 'policy_sha256': 'a' * 64,
                },
            ],
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
    second = build_capsule_handoff_worklist(plan=plan, related=related)
    assert first['inventory_sha256'] != second['inventory_sha256']
    related['resources'][0]['policy_sha256'] = '9' * 64
    third = build_capsule_handoff_worklist(plan=plan, related=related)
    assert second['inventory_sha256'] != third['inventory_sha256']


def test_worklist_digest_is_stable_for_resource_order_only():
    plan, related = _case()
    first = build_capsule_handoff_worklist(plan=plan, related=related)
    related['resources'].reverse()
    second = build_capsule_handoff_worklist(plan=plan, related=related)
    assert first['inventory_sha256'] == second['inventory_sha256']


def test_no_secret_or_rbac_subject_material_in_worklist():
    plan, related = _case()
    result = build_capsule_handoff_worklist(plan=plan, related=related)
    assert 'subjects' not in str(result)
    assert 'credential' not in str(result)
    assert len(result['inventory_sha256']) == 64

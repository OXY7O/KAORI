"""#1229 pure Capsule admission receipt: no false dry-run/live capability.

Authored-only fixtures. Do not execute tests or workflows during gate HOLD.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from app.kubernetes.tenant.capsule_handoff_admission import assess_capsule_handoff_admission
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.capsule_platform_admin_authority import _capsule_admin_scope
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint


def _fixture():
    now = datetime.now(UTC).isoformat()
    names = ['demo-dev']
    resources = []
    lists = [{
        'namespace': ns, 'kind': kind, 'list_resource_version': 'rv-101', 'count': 0,
    } for ns in names for kind in ('ResourceQuota', 'LimitRange', 'RoleBinding')]
    related_sha = _digest({'resources': resources, 'lists': lists})
    global_sha = _digest({
        'api_version': 'v1beta2', 'list_resource_version': 'cluster-list-rv',
        'resources': [],
    })
    lineage_sha = 'c' * 64
    components = [
        {
            'kind': 'CapsuleTenant', 'name': 'kaori-demo', 'uid': 'tenant-uid',
            'resource_version': '10', 'authority': 'capsule',
            'handoff': 'external_acceptance_required',
            'ownership': 'external_or_unattributed',
            'capsule_spec_sha256': 'a' * 64,
            'capsule_related_resources_sha256': related_sha,
            'capsule_related_resources_count': '0',
            'capsule_shared_quota_sha256': global_sha,
            'capsule_rbac_lineage_sha256': lineage_sha,
        },
        {
            'kind': 'Namespace', 'name': 'demo-dev', 'namespace': 'demo-dev',
            'uid': 'ns-uid', 'resource_version': '19',
            'authority': 'capsule', 'handoff': 'observe_only',
            'ownership': 'external_or_unattributed',
        },
    ]
    identity = [
        {'kind': 'CapsuleTenant', 'name': 'kaori-demo', 'uid': 'tenant-uid', 'resource_version': '10'},
        {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid', 'resource_version': '19'},
    ]
    plan = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1', 'generation': 7,
        'provider': 'capsule', 'handoff_fingerprint': handoff_fingerprint(components),
        'provider_identity': identity, 'successor_owner': 'platform-team',
        'change_reference': 'CHG-2026-1011',
        'requested_by': 10, 'requested_at': now,
        'handoff_components': components,
        'status': 'pending_independent_approval',
        'provider_mutation_performed': False,
        'provider_handoff_verified': False, 'release_authorized': False,
    }
    plan['plan_sha256'] = _plan_hash(plan)
    approval = {
        'status': 'acknowledged_pending_provider_handoff',
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'requested_by': 10, 'approved_by': 11, 'approved_at': now,
        'provider_handoff_verified': False, 'release_authorized': False,
    }
    scope = _capsule_admin_scope(components)
    acceptance = {
        'status': 'platform_admin_handoff_accepted',
        'authority_mode': 'capsule_platform_admin_governed',
        'tenant_id': plan['tenant_id'], 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'], 'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'provider_identity': identity, 'successor_owner': 'platform-team',
        'reviewed_by': 11, 'accepted_by': 12,
        'provider_username': 'cluster-admin', 'provider_groups': ['system:authenticated'],
        'provider_credential_id': 'X509SHA256=good-credential',
        'scoped_resources': scope, 'scope_count': len(scope),
        'consent_verified': True, 'verified_provider_identity': True,
        'resource_authority_verified': True,
        'authenticated_provider': 'kubernetes_self_subject_review',
        'authorization_source': 'kubernetes_self_subject_access_review',
        'accepted_at': now, 'provider_mutation_performed': False,
        'provider_handoff_verified': False, 'release_authorized': False,
        'secret_material_persisted': False,
    }
    preflight = {
        'tenant_id': plan['tenant_id'], 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'], 'provider': 'capsule',
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'live_provider_identity': identity, 'handoff_components': components,
        'checked_at': now, 'status': 'blocked',
        'blockers': ['Capsule controller-generated RoleBinding origins remain unverified.'],
        'dependency_counts': {
            'credentials': 0, 'Access Grants': 0, 'Memberships': 0,
            'enabled Groups': 0, 'managed resources': 0,
            'advanced capabilities': 0, 'domain reservations': 0,
            'exposure policies': 0,
        },
        'capsule_related_inventory': {
            'status': 'read_only_related_inventory',
            'resources': resources, 'resource_count': 0,
            'list_snapshots': lists, 'resource_sha256': related_sha,
            'blockers': [],
            'global_quota': {
                'status': 'observed_not_handoff_authorized',
                'scope_sha256': global_sha, 'resources': [], 'count': 0,
                'served_version': 'v1beta2',
                'list_resource_version': 'cluster-list-rv',
                'blockers': [],
            },
            'rbac_lineage': {
                'status': 'contract_correlated_controller_origin_unverified',
                'lineage_sha256': lineage_sha, 'contract_correlated': True,
                'controller_origin_verified': False, 'blockers': [],
            },
        },
    }
    authority = {
        'verification_source': 'kubernetes_self_subject_review',
        'authorization_source': 'kubernetes_self_subject_access_review',
        'provider_username': 'cluster-admin', 'provider_groups': ['system:authenticated'],
        'provider_credential_id': 'X509SHA256=good-credential',
        'cluster_id': 'cluster-1', 'scoped_resources': scope, 'scope_count': len(scope),
        'resource_authority_verified': True, 'provider_mutation_performed': False,
    }
    return {
        'tenant_id': 'tenant-1', 'actor_user_id': 12, 'plan': plan,
        'approval': approval, 'acceptance': acceptance,
        'preflight': preflight, 'provider_authority': authority,
    }


def _assess(case):
    return assess_capsule_handoff_admission(**case)


def test_complete_matching_snapshots_never_admit_dry_run_or_live_executor():
    result = _assess(_fixture())
    assert result['status'] == 'blocked_pending_capsule_provider_handoff'
    assert result['plan_sha256'] is not None
    assert result['provider_mutation_performed'] is False
    assert result['dry_run_admitted'] is False
    assert result['provider_execution_admitted'] is False
    assert result['provider_handoff_verified'] is False
    assert result['release_authorized'] is False
    assert result['resume_authorized'] is False
    assert 'rbac_controller_origin_unverified' in result['blockers']
    assert 'resource_specific_handoff_worklist_not_admitted' in result['blockers']
    assert 'provider_preflight_not_admitted' in result['blockers']


@pytest.mark.parametrize('field,mutation,expected', [
    ('plan', lambda p: p.update(requested_by=12), 'release_plan_changed_or_expired'),
    ('plan', lambda p: p['handoff_components'][0].update(resource_version='11'),
     'approved_capsule_scope_incomplete'),
    ('plan', lambda p: p.update(plan_sha256='a' * 64), 'release_plan_changed_or_expired'),
    ('approval', lambda a: a.update(approved_by=10), 'independent_approval_changed_or_expired'),
    ('approval', lambda a: a.update(status='pending'), 'independent_approval_changed_or_expired'),
    ('acceptance', lambda a: a.update(accepted_by=13), 'successor_acceptance_changed_or_expired'),
    ('acceptance', lambda a: a.update(consent_verified=False), 'successor_acceptance_changed_or_expired'),
    ('acceptance', lambda a: a.update(provider_credential_id='claimed'),
     'successor_acceptance_changed_or_expired'),
    ('preflight', lambda p: p.update(handoff_fingerprint='f' * 64),
     'provider_preflight_drift_or_stale'),
    ('provider_authority', lambda a: a.update(provider_credential_id='X509SHA256=rotated'),
     'provider_x509_ssr_sar_identity_changed'),
    ('provider_authority', lambda a: a.update(scoped_resources=[]),
     'provider_authority_scope_changed'),
])
def test_cross_evidence_drift_is_a_blocker(field, mutation, expected):
    case = _fixture()
    mutation(case[field])
    result = _assess(case)
    assert expected in result['blockers']
    assert result['dry_run_admitted'] is False


def test_stale_request_approval_acceptance_and_preflight_blocked():
    for field, key in [
        ('plan', 'requested_at'),
        ('approval', 'approved_at'),
        ('acceptance', 'accepted_at'),
        ('preflight', 'checked_at'),
    ]:
        case = _fixture()
        case[field][key] = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        outcome = _assess(case)
        assert outcome['blockers']
        assert outcome['dry_run_admitted'] is False


@pytest.mark.parametrize('tamper,expected', [
    (lambda p: p['capsule_related_inventory']['resources'].append({
        'kind': 'RoleBinding', 'namespace': 'demo-dev', 'name': 'unknown',
        'uid': 'u', 'resource_version': '2', 'origin': 'kaori_correlated',
    }), 'related_inventory_incomplete'),
    (lambda p: p['capsule_related_inventory']['list_snapshots'].pop(),
     'related_inventory_incomplete'),
    (lambda p: p['capsule_related_inventory']['global_quota'].update(scope_sha256='d' * 64),
     'global_quota_provenance_incomplete'),
    (lambda p: p['capsule_related_inventory']['rbac_lineage'].update(
        lineage_sha256='d' * 64), 'rbac_contract_not_correlated'),
])
def test_missing_related_scope_digest_or_revision_is_blocked(tamper, expected):
    case = _fixture()
    tamper(case['preflight'])
    result = _assess(case)
    assert expected in result['blockers']
    assert result['provider_execution_admitted'] is False


def test_forged_provider_controller_proof_never_opens_execution_gate():
    case = _fixture()
    case['preflight']['blockers'] = []
    case['preflight']['capsule_related_inventory']['rbac_lineage']['controller_origin_verified'] = True
    case['preflight']['capsule_related_inventory']['shared_quota_and_controller_origin_verified'] = True
    result = _assess(case)
    assert 'rbac_controller_origin_unverified' in result['blockers']
    assert 'resource_specific_handoff_worklist_not_admitted' in result['blockers']
    assert result['provider_execution_admitted'] is False


def test_partial_missing_snapshots_or_forged_actor_never_raise_open_authorization():
    case = _fixture()
    case['approval'] = None
    case['provider_authority'] = None
    case['actor_user_id'] = 999
    result = _assess(case)
    assert 'independent_approval_missing' in result['blockers']
    assert 'fresh_provider_authority_missing' in result['blockers']
    assert result['release_authorized'] is False


def test_snapshots_never_leak_principal_or_credentials_into_gate_summary():
    case = _fixture()
    outcome = _assess(case)
    assert 'cluster-admin' not in str(outcome)
    assert 'X509SHA256=good-credential' not in str(outcome)
    assert 'platform-team' not in str(outcome)
    assert outcome['secret_material_persisted'] is False

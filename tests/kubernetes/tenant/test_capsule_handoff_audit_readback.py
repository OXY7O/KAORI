"""Source-only audit and provider read-back regressions for Capsule handoff #1229.

Authored only: no CI/CD, pytest, live Kubernetes API or AuditEvent writes.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_handoff_audit_envelope import (
    inspect_capsule_audit_event_envelopes,
)
from app.kubernetes.tenant.capsule_handoff_attempt_state import _event_checksum
from app.kubernetes.tenant.capsule_handoff_readback_evidence import (
    inspect_capsule_readback_candidate,
)
from app.kubernetes.tenant.capsule_handoff_recovery import capture_capsule_namespace_baseline
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import (
    _capsule_spec_sha256, handoff_fingerprint,
)


def _namespace(version='9'):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='demo-dev', uid='ns-uid', resource_version=version,
            labels={
                'app.kubernetes.io/managed-by': 'kaori',
                'kaori.io/tenant-id': 'tenant-1',
                'capsule.clastix.io/tenant': 'demo',
                'third-party.example/retained': 'yes',
            },
            annotations={'third-party.example/keep': 'true'},
            owner_references=[{'kind': 'Tenant', 'name': 'demo'}],
            finalizers=['capsule.clastix.io/protect'],
            generation=1, deletion_timestamp=None,
            deletion_grace_period_seconds=None,
        ),
        spec={'finalizers': ['kubernetes']},
    )


def _inputs():
    spec = {'resourceQuotas': {'scope': 'Tenant'}}
    lists = [
        {'namespace': 'demo-dev', 'kind': kind,
         'list_resource_version': 'list-rv', 'count': 0}
        for kind in ('LimitRange', 'ResourceQuota', 'RoleBinding')
    ]
    related_sha = _digest({'resources': [], 'lists': lists})
    global_quota = {
        'status': 'observed_not_handoff_authorized',
        'served_version': 'v1beta2', 'list_resource_version': 'global-rv',
        'resources': [], 'count': 0, 'blockers': [],
    }
    global_quota['scope_sha256'] = _digest({
        'api_version': 'v1beta2',
        'list_resource_version': 'global-rv', 'resources': [],
    })
    components = [
        {
            'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid',
            'resource_version': '3', 'authority': 'capsule',
            'ownership': 'external_or_unattributed',
            'handoff': 'external_acceptance_required',
            'capsule_spec_sha256': _capsule_spec_sha256(spec),
            'capsule_related_resources_sha256': related_sha,
            'capsule_related_resources_count': '0',
            'capsule_shared_quota_sha256': global_quota['scope_sha256'],
            'capsule_rbac_lineage_sha256': 'a' * 64,
        },
        {
            'kind': 'Namespace', 'name': 'demo-dev', 'namespace': 'demo-dev',
            'uid': 'ns-uid', 'resource_version': '9',
            'authority': 'capsule', 'ownership': 'kaori_marker_correlated',
            'handoff': 'external_acceptance_required',
        },
    ]
    related = {
        'status': 'read_only_related_inventory',
        'resources': [], 'resource_count': 0,
        'list_snapshots': lists, 'resource_sha256': related_sha,
        'global_quota': global_quota,
        'rbac_lineage': {
            'status': 'contract_correlated_controller_origin_unverified',
            'lineage_sha256': 'a' * 64,
            'contract_correlated': True, 'controller_origin_verified': False,
            'blockers': [],
        },
    }
    plan = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1', 'generation': 7,
        'provider': 'capsule', 'requested_by': 10,
        'requested_at': datetime.now(UTC).isoformat(),
        'provider_identity': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '3'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid', 'resource_version': '9'},
        ],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-1011', 'handoff_components': components,
        'handoff_fingerprint': handoff_fingerprint(components),
    }
    plan['plan_sha256'] = _plan_hash(plan)
    cr = {
        'metadata': {
            'name': 'demo', 'uid': 'cr-uid', 'resourceVersion': '3',
            'labels': {'capsule.clastix.io/tenant': 'demo'},
        },
        'spec': spec,
    }
    original_namespace = _namespace()
    baseline = capture_capsule_namespace_baseline(
        components[1], original_namespace, tenant_id='tenant-1',
        capsule_tenant_name='demo',
    )
    return plan, related, cr, original_namespace, baseline


def _readback(plan, related, cr, namespace, baseline, *, current_related=None):
    return inspect_capsule_readback_candidate(
        plan=plan, source_related=related,
        current_related=current_related if current_related is not None else related,
        current_capsule_cr=cr, current_namespaces={'demo-dev': namespace},
        namespace_baselines=[baseline], tenant_id='tenant-1',
    )


def test_readback_observation_remains_untrusted_even_when_everything_is_unchanged():
    plan, related, cr, ns, baseline = _inputs()
    result = _readback(plan, related, cr, ns, baseline)
    assert result['expected_count'] == 1
    assert result['pending_count'] == 1
    assert result['transferred_count'] == 0
    assert result['ambiguous_count'] == 0
    assert result['provider_snapshot_authenticity_verified'] is False
    assert result['provider_handoff_verified'] is False
    assert result['release_authorized'] is False
    assert 'provider_execution_authority_unverified' in result['blockers']
    assert 'third-party.example' not in str(result)
    assert len(result['readback_sha256']) == 64


def test_candidate_successor_marker_readback_does_not_prove_approval_or_release():
    plan, related, cr, ns, baseline = _inputs()
    changed = deepcopy(ns)
    changed.metadata.resource_version = '10'
    changed.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
    del changed.metadata.labels['kaori.io/tenant-id']
    result = _readback(plan, related, cr, changed, baseline)
    assert result['transferred_count'] == 1
    assert result['provider_handoff_verified'] is False
    assert result['resume_authorized'] is False
    assert result['status'] == 'readback_candidate_recovery_review_required'


def test_capsule_cr_spec_uid_or_foreign_namespace_drift_cannot_be_silent():
    plan, related, cr, ns, baseline = _inputs()
    changed_cr = deepcopy(cr)
    changed_cr['spec']['resourceQuotas']['scope'] = 'Other'
    result = _readback(plan, related, changed_cr, ns, baseline)
    assert 'capsule_cr_provider_spec_or_identity_drift' in result['blockers']
    changed_ns = deepcopy(ns)
    changed_ns.metadata.annotations['third-party.example/keep'] = 'tampered'
    result = _readback(plan, related, cr, changed_ns, baseline)
    assert 'namespace_ownership_or_preservation_drift' in result['blockers']


def test_missing_namespace_or_baseline_scope_fails_closed():
    plan, related, cr, ns, baseline = _inputs()
    with pytest.raises(ValueError):
        inspect_capsule_readback_candidate(
            plan=plan, source_related=related, current_related=related,
            current_capsule_cr=cr, current_namespaces={},
            namespace_baselines=[baseline], tenant_id='tenant-1',
        )
    with pytest.raises(ValueError):
        inspect_capsule_readback_candidate(
            plan=plan, source_related=related, current_related=related,
            current_capsule_cr=cr, current_namespaces={'demo-dev': ns},
            namespace_baselines=[], tenant_id='tenant-1',
        )


def test_related_provider_list_and_global_quota_revisions_are_detected():
    plan, related, cr, ns, baseline = _inputs()
    changed = deepcopy(related)
    changed['list_snapshots'][0]['list_resource_version'] = 'new-rv'
    changed['resource_sha256'] = _digest({
        'resources': changed['resources'], 'lists': changed['list_snapshots'],
    })
    receipt = _readback(plan, related, cr, ns, baseline, current_related=changed)
    assert 'namespaced_provider_object_or_list_changed' in receipt['blockers']
    changed = deepcopy(related)
    changed['global_quota']['list_resource_version'] = 'updated'
    changed['global_quota']['scope_sha256'] = _digest({
        'api_version': 'v1beta2', 'list_resource_version': 'updated', 'resources': [],
    })
    receipt = _readback(plan, related, cr, ns, baseline, current_related=changed)
    assert 'cluster_global_quota_or_list_changed' in receipt['blockers']


def test_readback_rejects_forged_unrecomputed_inventory_hash():
    plan, related, cr, ns, baseline = _inputs()
    changed = deepcopy(related)
    changed['list_snapshots'].pop()
    with pytest.raises(ValueError):
        _readback(plan, related, cr, ns, baseline, current_related=changed)


def _audit_start(plan, related, *, at):
    worklist = build_capsule_handoff_worklist(plan=plan, related=related)
    event = {
        'contract_version': 'capsule-handoff-attempt/v1',
        'event_type': 'started',
        'attempt_id': '00000000-0000-4000-8000-000000000001',
        'sequence': 1, 'event_at': at.isoformat(),
        'tenant_id': plan['tenant_id'], 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'], 'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': worklist['inventory_sha256'],
        'actor_user_id': 30, 'previous_event_sha256': None,
        'event_sha256': None, 'outcome': 'unknown',
        'readback_sha256': None, 'expected_count': 1,
        'observed_count': 0, 'pending_count': 0, 'transferred_count': 0,
        'ambiguous_count': 0, 'provider_handoff_verified': False,
        'release_authorized': False, 'resume_authorized': False,
        'auto_retry_authorized': False, 'secret_material_persisted': False,
    }
    event['event_sha256'] = _event_checksum(event)
    return event


def _audit_projection(plan, related, rows):
    return inspect_capsule_audit_event_envelopes(
        plan=plan, related=related, accepted_actor_user_id=30, rows=rows,
    )


def test_audit_event_db_envelope_checks_row_actor_action_and_chained_receipt():
    plan, related, *_ = _inputs()
    now = datetime.now(UTC)
    event = _audit_start(plan, related, at=now)
    row = {
        'id': 45, 'actor_user_id': 30, 'target_type':
        'kubernetes_tenant_release_capsule_handoff_execution',
        'target_id': 'tenant-1',
        'action': 'tenant.release.capsule_handoff_started',
        'created_at': now + timedelta(seconds=1),
        'metadata_json': event,
    }
    result = _audit_projection(plan, related, [row])
    assert result['status'] == 'started_outcome_unknown_recovery_required'
    assert result['audit_schema_validated'] is True
    assert result['audit_storage_append_only_verified'] is False
    assert result['audit_stream_completeness_verified'] is False
    assert result['readback_authoritative_verified'] is False
    assert result['provider_execution_admitted'] is False


@pytest.mark.parametrize('change', [
    lambda row: row.update(id=0),
    lambda row: row.update(actor_user_id=31),
    lambda row: row.update(target_id='other-tenant'),
    lambda row: row.update(action='tenant.release.capsule_handoff_verified'),
    lambda row: row.update(created_at=datetime.now(UTC) - timedelta(days=1)),
    lambda row: row['metadata_json'].update(secret='password-not-a-field'),
    lambda row: row['metadata_json'].update(provider_handoff_verified=True),
])
def test_invalid_audit_envelopes_never_look_trusted(change):
    plan, related, *_ = _inputs()
    now = datetime.now(UTC)
    row = {
        'id': 50, 'actor_user_id': 30,
        'target_type': 'kubernetes_tenant_release_capsule_handoff_execution',
        'target_id': 'tenant-1',
        'action': 'tenant.release.capsule_handoff_started',
        'created_at': now + timedelta(seconds=1),
        'metadata_json': _audit_start(plan, related, at=now),
    }
    change(row)
    with pytest.raises((TypeError, ValueError)):
        _audit_projection(plan, related, [row])


def test_missing_audit_rows_do_not_grant_execution_or_claim_stream_completeness():
    plan, related, *_ = _inputs()
    result = _audit_projection(plan, related, [])
    assert result['status'] == 'no_attempt_observed_not_authorized'
    assert result['audit_stream_completeness_verified'] is False
    assert result['resume_authorized'] is False
    assert result['release_authorized'] is False

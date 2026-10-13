"""Source-only audit and provider read-back regressions for Capsule handoff #1229.

Authored only: no CI/CD, pytest, live Kubernetes API or AuditEvent writes.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_handoff_attempt_state import _event_checksum
from app.kubernetes.tenant.capsule_handoff_audit_envelope import (
    inspect_capsule_audit_event_envelopes,
    inspect_capsule_audit_readback_link,
    inspect_capsule_scope_g2g3_trace,
)
from app.kubernetes.tenant.capsule_handoff_dry_run import (
    build_capsule_scope_patch_review,
    inspect_capsule_complete_dry_run_shapes,
)
from app.kubernetes.tenant.capsule_handoff_readback_evidence import (
    inspect_capsule_readback_candidate,
)
from app.kubernetes.tenant.capsule_handoff_recovery import capture_capsule_namespace_baseline
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    _digest,
    capsule_related_scope_sha256,
    classify_capsule_related_resource,
)
from app.kubernetes.tenant.capsule_handoff_resource_admission import (
    assess_capsule_resource_handoff_scope,
)
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import (
    _capsule_spec_sha256,
    handoff_fingerprint,
)


def _namespace(version='9'):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='demo-dev',
            uid='ns-uid',
            resource_version=version,
            labels={
                'app.kubernetes.io/managed-by': 'kaori',
                'kaori.io/tenant-id': 'tenant-1',
                'capsule.clastix.io/tenant': 'demo',
                'third-party.example/retained': 'yes',
            },
            annotations={'third-party.example/keep': 'true'},
            owner_references=[{'kind': 'Tenant', 'name': 'demo'}],
            finalizers=['capsule.clastix.io/protect'],
            generation=1,
            deletion_timestamp=None,
            deletion_grace_period_seconds=None,
        ),
        spec={'finalizers': ['kubernetes']},
    )


def _inputs():
    spec = {'resourceQuotas': {'scope': 'Tenant'}}
    lists = [
        {'namespace': 'demo-dev', 'kind': kind, 'list_resource_version': 'list-rv', 'count': 0}
        for kind in ('LimitRange', 'ResourceQuota', 'RoleBinding')
    ]
    related_sha = capsule_related_scope_sha256(resources=[], list_snapshots=lists)
    global_quota = {
        'status': 'observed_not_handoff_authorized',
        'served_version': 'v1beta2',
        'list_resource_version': 'global-rv',
        'resources': [],
        'count': 0,
        'blockers': [],
    }
    global_quota['scope_sha256'] = _digest(
        {
            'api_version': 'v1beta2',
            'resources': [],
        }
    )
    components = [
        {
            'kind': 'CapsuleTenant',
            'name': 'demo',
            'uid': 'cr-uid',
            'resource_version': '3',
            'authority': 'capsule',
            'ownership': 'external_or_unattributed',
            'handoff': 'external_acceptance_required',
            'capsule_spec_sha256': _capsule_spec_sha256(spec),
            'capsule_related_resources_sha256': related_sha,
            'capsule_related_resources_count': '0',
            'capsule_shared_quota_sha256': global_quota['scope_sha256'],
            'capsule_rbac_lineage_sha256': 'a' * 64,
        },
        {
            'kind': 'Namespace',
            'name': 'demo-dev',
            'namespace': 'demo-dev',
            'uid': 'ns-uid',
            'resource_version': '9',
            'authority': 'capsule',
            'ownership': 'kaori_marker_correlated',
            'handoff': 'external_acceptance_required',
        },
    ]
    related = {
        'status': 'read_only_related_inventory',
        'resources': [],
        'resource_count': 0,
        'blockers': [],
        'list_snapshots': lists,
        'resource_sha256': related_sha,
        'global_quota': global_quota,
        'rbac_lineage': {
            'status': 'contract_correlated_controller_origin_unverified',
            'lineage_sha256': 'a' * 64,
            'contract_correlated': True,
            'controller_origin_verified': False,
            'blockers': [],
        },
    }
    plan = {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'generation': 7,
        'provider': 'capsule',
        'requested_by': 10,
        'requested_at': datetime.now(UTC).isoformat(),
        'provider_identity': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '3'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid', 'resource_version': '9'},
        ],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-1011',
        'handoff_components': components,
        'handoff_fingerprint': handoff_fingerprint(components),
    }
    plan['plan_sha256'] = _plan_hash(plan)
    cr = {
        'metadata': {
            'name': 'demo',
            'uid': 'cr-uid',
            'resourceVersion': '3',
            'labels': {'capsule.clastix.io/tenant': 'demo'},
        },
        'spec': spec,
    }
    original_namespace = _namespace()
    baseline = capture_capsule_namespace_baseline(
        components[1],
        original_namespace,
        tenant_id='tenant-1',
        capsule_tenant_name='demo',
    )
    return plan, related, cr, original_namespace, baseline


def _readback(plan, related, cr, namespace, baseline, *, current_related=None):
    return inspect_capsule_readback_candidate(
        plan=plan,
        source_related=related,
        current_related=current_related if current_related is not None else related,
        current_capsule_cr=cr,
        current_namespaces={'demo-dev': namespace},
        namespace_baselines=[baseline],
        tenant_id='tenant-1',
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
            plan=plan,
            source_related=related,
            current_related=related,
            current_capsule_cr=cr,
            current_namespaces={},
            namespace_baselines=[baseline],
            tenant_id='tenant-1',
        )
    with pytest.raises(ValueError):
        inspect_capsule_readback_candidate(
            plan=plan,
            source_related=related,
            current_related=related,
            current_capsule_cr=cr,
            current_namespaces={'demo-dev': ns},
            namespace_baselines=[],
            tenant_id='tenant-1',
        )


def test_related_provider_list_and_global_quota_revisions_are_detected():
    plan, related, cr, ns, baseline = _inputs()
    changed = deepcopy(related)
    changed['list_snapshots'][0]['list_resource_version'] = 'new-rv'
    changed['resource_sha256'] = capsule_related_scope_sha256(
        resources=changed['resources'],
        list_snapshots=changed['list_snapshots'],
    )
    receipt = _readback(plan, related, cr, ns, baseline, current_related=changed)
    assert 'namespaced_provider_object_or_list_changed' in receipt['blockers']
    changed = deepcopy(related)
    changed['global_quota']['list_resource_version'] = 'updated'
    changed['global_quota']['scope_sha256'] = _digest(
        {
            'api_version': 'v1beta2',
            'resources': [],
        }
    )
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
        'sequence': 1,
        'event_at': at.isoformat(),
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': worklist['inventory_sha256'],
        'actor_user_id': 30,
        'previous_event_sha256': None,
        'event_sha256': None,
        'outcome': 'unknown',
        'readback_sha256': None,
        'expected_count': 1,
        'observed_count': 0,
        'pending_count': 0,
        'transferred_count': 0,
        'ambiguous_count': 0,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'resume_authorized': False,
        'auto_retry_authorized': False,
        'secret_material_persisted': False,
    }
    event['event_sha256'] = _event_checksum(event)
    return event


def _audit_projection(plan, related, rows):
    return inspect_capsule_audit_event_envelopes(
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        rows=rows,
    )


def test_audit_event_db_envelope_checks_row_actor_action_and_chained_receipt():
    plan, related, *_ = _inputs()
    now = datetime.now(UTC)
    event = _audit_start(plan, related, at=now)
    row = {
        'id': 45,
        'actor_user_id': 30,
        'target_type': 'kubernetes_tenant_release_capsule_handoff_execution',
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


@pytest.mark.parametrize(
    'change',
    [
        lambda row: row.update(id=0),
        lambda row: row.update(actor_user_id=31),
        lambda row: row.update(target_id='other-tenant'),
        lambda row: row.update(action='tenant.release.capsule_handoff_verified'),
        lambda row: row.update(created_at=datetime.now(UTC) - timedelta(days=1)),
        lambda row: row['metadata_json'].update(secret='password-not-a-field'),
        lambda row: row['metadata_json'].update(provider_handoff_verified=True),
    ],
)
def test_invalid_audit_envelopes_never_look_trusted(change):
    plan, related, *_ = _inputs()
    now = datetime.now(UTC)
    row = {
        'id': 50,
        'actor_user_id': 30,
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


def test_audit_readback_link_matches_count_but_never_trusts_source_or_executes():
    plan, related, cr, ns, baseline = _inputs()
    candidate = _readback(plan, related, cr, ns, baseline)
    now = datetime.now(UTC)
    started = _audit_start(plan, related, at=now)
    observed = deepcopy(started)
    observed.update(
        {
            'event_type': 'readback_candidate',
            'sequence': 2,
            'event_at': (now + timedelta(seconds=2)).isoformat(),
            'previous_event_sha256': started['event_sha256'],
            'outcome': 'readback_observed',
            'readback_sha256': candidate['readback_sha256'],
            'expected_count': candidate['expected_count'],
            'observed_count': candidate['observed_count'],
            'pending_count': candidate['pending_count'],
            'transferred_count': candidate['transferred_count'],
            'ambiguous_count': candidate['ambiguous_count'],
        }
    )
    observed['event_sha256'] = _event_checksum(observed)
    rows = [
        {
            'id': 80,
            'actor_user_id': 30,
            'target_type': 'kubernetes_tenant_release_capsule_handoff_execution',
            'target_id': 'tenant-1',
            'action': 'tenant.release.capsule_handoff_started',
            'created_at': now + timedelta(seconds=1),
            'metadata_json': started,
        },
        {
            'id': 81,
            'actor_user_id': 30,
            'target_type': 'kubernetes_tenant_release_capsule_handoff_execution',
            'target_id': 'tenant-1',
            'action': 'tenant.release.capsule_handoff_readback_candidate',
            'created_at': now + timedelta(seconds=3),
            'metadata_json': observed,
        },
    ]
    matched = inspect_capsule_audit_readback_link(
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        rows=rows,
        readback_candidate=candidate,
    )
    assert matched['status'] == 'readback_claim_correlated_unverified'
    assert matched['recorded_readback_matches_candidate'] is True
    assert matched['audit_storage_append_only_verified'] is False
    assert matched['readback_authoritative_verified'] is False
    assert matched['resume_authorized'] is False
    assert matched['release_authorized'] is False
    tampered = dict(candidate, readback_sha256='e' * 64)
    with pytest.raises(ValueError):
        inspect_capsule_audit_readback_link(
            plan=plan,
            related=related,
            accepted_actor_user_id=30,
            rows=rows,
            readback_candidate=tampered,
        )


def test_audit_readback_link_does_not_infer_completed_scope_from_started_alone():
    plan, related, cr, ns, baseline = _inputs()
    now = datetime.now(UTC)
    started = _audit_start(plan, related, at=now)
    rows = [
        {
            'id': 90,
            'actor_user_id': 30,
            'target_type': 'kubernetes_tenant_release_capsule_handoff_execution',
            'target_id': 'tenant-1',
            'action': 'tenant.release.capsule_handoff_started',
            'created_at': now + timedelta(seconds=1),
            'metadata_json': started,
        }
    ]
    result = inspect_capsule_audit_readback_link(
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        rows=rows,
        readback_candidate=_readback(plan, related, cr, ns, baseline),
    )
    assert result['recorded_readback_matches_candidate'] is False
    assert result['status'] == 'no_complete_readback_claim'


def _full_related_case(kind='ResourceQuota', *, include_foreign=False):
    """One full canonical Capsule LIST plus optional protected foreign control."""
    plan, related, cr, namespace, baseline = _inputs()
    labels = {
        'app.kubernetes.io/managed-by': 'kaori',
        'kaori.io/tenant-id': plan['tenant_id'],
        'capsule.clastix.io/tenant': 'demo',
        'foreign.example/keep': 'untouched',
    }
    if kind == 'RoleBinding':
        labels['kaori.io/access-grant'] = 'grant-1'

    def object_with(name, manager='kaori'):
        obj = SimpleNamespace(
            metadata=SimpleNamespace(
                name=name,
                namespace='demo-dev',
                uid='uid-' + name,
                resource_version='15',
                labels=deepcopy(labels)
                if manager == 'kaori'
                else {
                    'app.kubernetes.io/managed-by': manager,
                    'capsule.clastix.io/tenant': 'demo',
                    'foreign.example/keep': 'untouched',
                },
                annotations={'external.example/note': 'preserve'},
                owner_references=[
                    {
                        'kind': 'Tenant',
                        'apiVersion': 'capsule.clastix.io/v1beta2',
                        'name': 'demo',
                        'uid': 'cr-uid',
                    }
                ],
                finalizers=['capsule.clastix.io/preserve'],
            )
        )
        if kind == 'RoleBinding':
            obj.role_ref = {
                'kind': 'ClusterRole',
                'name': 'view',
                'apiGroup': 'rbac.authorization.k8s.io',
            }
            obj.subjects = [
                {
                    'kind': 'ServiceAccount',
                    'namespace': 'demo-dev',
                    'name': 'existing-serviceaccount',
                }
            ]
        elif kind == 'ResourceQuota':
            obj.spec = {'hard': {'requests.cpu': '2'}}
        else:
            obj.spec = {'limits': [{'type': 'Container', 'max': {'memory': '1Gi'}}]}
        return obj

    before = object_with('controlled')
    foreign = object_with('external-control', manager='provider') if include_foreign else None

    def projected(obj):
        result, _ = classify_capsule_related_resource(
            resource=obj,
            kind=kind,
            namespace='demo-dev',
            tenant_id=plan['tenant_id'],
            capsule_name='demo',
            capsule_uid='cr-uid',
        )
        return result

    source_rows = [projected(before)] + ([projected(foreign)] if foreign else [])
    source_rows.sort(key=lambda x: (x['namespace'], x['kind'], x['name']))
    related['resources'] = source_rows
    related['resource_count'] = len(source_rows)
    for entry in related['list_snapshots']:
        if entry['kind'] == kind:
            entry['count'] = len(source_rows)
    related['resource_sha256'] = capsule_related_scope_sha256(
        resources=related['resources'],
        list_snapshots=related['list_snapshots'],
    )
    plan['handoff_components'][0]['capsule_related_resources_sha256'] = related['resource_sha256']
    plan['handoff_components'][0]['capsule_related_resources_count'] = str(len(source_rows))
    plan['handoff_fingerprint'] = handoff_fingerprint(plan['handoff_components'])
    plan['plan_sha256'] = _plan_hash(plan)
    updated = deepcopy(before)
    updated.metadata.resource_version = '16'
    updated.metadata.labels = {
        key: val
        for key, val in labels.items()
        if not key.startswith('kaori.io/') and key != 'app.kubernetes.io/managed-by'
    }
    updated.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
    current = deepcopy(related)
    current['resources'] = [projected(updated)] + ([projected(foreign)] if foreign else [])
    current['resources'].sort(key=lambda x: (x['namespace'], x['kind'], x['name']))
    for entry in current['list_snapshots']:
        if entry['kind'] == kind:
            entry['list_resource_version'] = 'list-after-handoff'
    current['resource_sha256'] = capsule_related_scope_sha256(
        resources=current['resources'],
        list_snapshots=current['list_snapshots'],
    )
    key = ('demo-dev', kind, 'controlled')
    evidence = {
        key: {
            'before': before,
            'current': updated,
            'approved_label_keys': [
                k for k in labels if k.startswith('kaori.io/') or k == 'app.kubernetes.io/managed-by'
            ],
        },
    }
    return plan, related, current, cr, namespace, baseline, evidence, foreign


def _full_readback(case, *, current=None, evidence='provided'):
    plan, source, after, cr, namespace, baseline, snapshots, _foreign = case
    return inspect_capsule_readback_candidate(
        plan=plan,
        source_related=source,
        current_related=after if current is None else current,
        current_capsule_cr=cr,
        current_namespaces={'demo-dev': namespace},
        namespace_baselines=[baseline],
        tenant_id=plan['tenant_id'],
        related_transfer_evidence=(snapshots if evidence == 'provided' else evidence),
    )


@pytest.mark.parametrize('kind', ('ResourceQuota', 'LimitRange', 'RoleBinding'))
def test_whole_scope_explains_exact_related_metadata_transfer_without_list_drift(kind):
    case = _full_related_case(kind, include_foreign=True)
    observed = _full_readback(case)
    assert observed['expected_count'] == 2
    assert observed['pending_count'] == 1  # Namespace not transferred yet
    assert observed['transferred_count'] == 1
    assert observed['ambiguous_count'] == 0
    assert observed['related_transfer_candidate_count'] == 1
    assert observed['related_resource_observations'][0]['state'] == 'provider_markers_transferred'
    assert 'namespaced_provider_object_or_list_changed' not in observed['blockers']
    assert 'namespaced_list_revision_drift' not in observed['blockers']
    assert 'related_foreign_or_unadmitted_control_drift' not in observed['blockers']
    assert observed['provider_snapshot_authenticity_verified'] is False
    assert observed['provider_handoff_verified'] is False
    assert observed['release_authorized'] is False
    assert 'existing-serviceaccount' not in str(observed)


def test_whole_scope_changed_digest_without_complete_object_evidence_is_ambiguous():
    case = _full_related_case()
    result = _full_readback(case, evidence=None)
    assert result['expected_count'] == 2
    assert result['transferred_count'] == 0
    assert result['ambiguous_count'] == 1
    assert 'related_kaori_control_recovery_unverified' in result['blockers']
    assert result['auto_retry_authorized'] is False


@pytest.mark.parametrize('change', ('policy', 'foreign_label', 'foreign_rv', 'owner'))
def test_whole_scope_foreign_control_or_policy_change_remains_a_blocker(change):
    case = _full_related_case(include_foreign=True)
    after = deepcopy(case[2])
    if change == 'policy':
        controlled = next(row for row in after['resources'] if row['name'] == 'controlled')
        controlled['policy_sha256'] = 'f' * 64
    elif change == 'foreign_label':
        other = next(row for row in after['resources'] if row['name'] == 'external-control')
        other['metadata_sha256'] = 'a' * 64
    elif change == 'foreign_rv':
        other = next(row for row in after['resources'] if row['name'] == 'external-control')
        other['resource_version'] = 'changed-by-other-actor'
    else:
        other = next(row for row in after['resources'] if row['name'] == 'external-control')
        other['origin'] = 'ambiguous_kaori'
    after['resource_sha256'] = capsule_related_scope_sha256(
        resources=after['resources'],
        list_snapshots=after['list_snapshots'],
    )
    result = _full_readback(case, current=after)
    assert result['ambiguous_count'] or 'related_foreign_or_unadmitted_control_drift' in result['blockers']
    assert result['provider_handoff_verified'] is False


def test_whole_scope_partial_evidence_and_missing_or_duplicated_list_fail_closed():
    case = _full_related_case()
    with pytest.raises(ValueError, match='cover exactly'):
        _full_readback(case, evidence={})
    current = deepcopy(case[2])
    current['list_snapshots'].pop()
    with pytest.raises(ValueError):
        _full_readback(case, current=current)


def test_whole_scope_does_not_accept_unexplained_list_revision_or_grq_drift():
    case = _full_related_case('LimitRange')
    current = deepcopy(case[2])
    for row in current['list_snapshots']:
        if row['kind'] == 'ResourceQuota':
            row['list_resource_version'] = 'foreign-list-change'
    current['resource_sha256'] = capsule_related_scope_sha256(
        resources=current['resources'],
        list_snapshots=current['list_snapshots'],
    )
    receipt = _full_readback(case, current=current)
    assert 'namespaced_list_revision_drift' in receipt['blockers']
    current = deepcopy(case[2])
    current['global_quota']['list_resource_version'] = 'changed'
    current['global_quota']['scope_sha256'] = _digest(
        {
            'api_version': 'v1beta2',
            'resources': [],
        }
    )
    receipt = _full_readback(case, current=current)
    assert 'cluster_global_quota_or_list_changed' in receipt['blockers']
    assert receipt['release_authorized'] is False


def test_whole_scope_premature_transfer_without_list_revision_is_blocked():
    case = _full_related_case('RoleBinding')
    current = deepcopy(case[2])
    for row in current['list_snapshots']:
        if row['kind'] == 'RoleBinding':
            row['list_resource_version'] = 'list-rv'
    current['resource_sha256'] = capsule_related_scope_sha256(
        resources=current['resources'],
        list_snapshots=current['list_snapshots'],
    )
    receipt = _full_readback(case, current=current)
    assert 'related_transfer_list_revision_not_observed' in receipt['blockers']
    assert receipt['provider_handoff_verified'] is False


def test_whole_scope_rejects_extra_list_fields_even_with_valid_transfer_and_rehash():
    case = _full_related_case()
    current = deepcopy(case[2])
    for row in current['list_snapshots']:
        if row['kind'] == 'ResourceQuota':
            row['unreviewed_watch_token'] = 'caller-injected'
    current['resource_sha256'] = capsule_related_scope_sha256(
        resources=current['resources'],
        list_snapshots=current['list_snapshots'],
    )
    result = _full_readback(case, current=current)
    assert 'related_list_schema_scope_or_count_changed' in result['blockers']
    assert result['provider_handoff_verified'] is False
    assert 'caller-injected' not in str(result)


def _g2_source_case():
    plan, related, cr, namespace, baseline = _inputs()
    report = assess_capsule_resource_handoff_scope(plan=plan, related=related)
    now = datetime.now(UTC).isoformat()
    approval = {
        'status': 'acknowledged_pending_provider_handoff',
        'plan_sha256': plan['plan_sha256'],
        'approved_by': 11,
        'requested_by': plan['requested_by'],
        'approved_at': now,
        'provider_handoff_verified': False,
        'release_authorized': False,
    }
    acceptance = {
        'status': 'platform_admin_handoff_accepted',
        'accepted_by': 12,
        'reviewed_by': 11,
        'plan_sha256': plan['plan_sha256'],
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'accepted_at': now,
        'consent_verified': True,
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
    candidates = [
        row for row in report['resources'] if row['inventory_decision'] == 'candidate_kaori_metadata_handoff_review'
    ]
    assert len(candidates) == 1
    target = candidates[0]
    manifest = {
        'contract_version': 'capsule-resource-successor-consent/v1',
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': report['worklist_sha256'],
        'resource_review_sha256': report['resource_review_sha256'],
        'change_reference': plan['change_reference'],
        'reviewed_by': 11,
        'accepted_by': 12,
        'accepted_at': now,
        'transfer_targets': [
            {
                'kind': 'Namespace',
                'namespace': '',
                'name': target['name'],
                'uid': target['uid'],
                'resource_version': target['resource_version'],
                'policy_sha256': None,
                'metadata_sha256': None,
                'decision': 'proposed_metadata_labels_only',
                'proposed_label_keys': [
                    'app.kubernetes.io/managed-by',
                    'kaori.io/tenant-id',
                ],
            }
        ],
    }
    source = {
        'plan': plan,
        'related': related,
        'current_capsule_cr': cr,
        'source_namespaces': {'demo-dev': namespace},
        'source_related_objects': {},
        'approval': approval,
        'acceptance': acceptance,
        'consent_manifest': manifest,
    }
    preview = deepcopy(namespace)
    preview.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
    preview.metadata.labels.pop('kaori.io/tenant-id')
    return source, {('', 'Namespace', 'demo-dev'): preview}, baseline


def test_g2_complete_offline_scope_binds_only_original_namespace_and_capsule_cr():
    source, previews, baseline = _g2_source_case()
    review = build_capsule_scope_patch_review(**source)
    assert review['status'] == 'complete_offline_scope_patch_review_unadmitted'
    assert review['transfer_candidate_count'] == 1
    assert review['complete_scope_count'] == 2
    assert review['globally_preserved_count'] == 1
    assert {item['kind']: item['operation'] for item in review['scope_items']} == {
        'CapsuleTenant': 'preserve_source_only_unverified',
        'Namespace': 'conditional_metadata_dry_run_candidate',
    }
    assert review['global_quota_provider_readback_verified'] is False
    assert review['provider_execution_admitted'] is False
    receipt = inspect_capsule_complete_dry_run_shapes(
        **source,
        preview_objects=previews,
    )
    assert receipt['preview_count'] == 1
    assert receipt['scope_items_sha256'] == review['scope_items_sha256']
    assert receipt['server_dry_run_completed'] is False
    assert receipt['release_authorized'] is False


@pytest.mark.parametrize(
    'mutation', ['missing_preview', 'extra_target', 'wrong_labels', 'stale_resource', 'missing_consent', 'foreign_raw']
)
def test_g2_offline_source_rejects_partial_preview_or_stale_consent(mutation):
    source, previews, _ = _g2_source_case()
    if mutation == 'missing_preview':
        previews.clear()
    elif mutation == 'extra_target':
        previews[('demo-dev', 'RoleBinding', 'foreign')] = {}
    elif mutation == 'wrong_labels':
        previews[('', 'Namespace', 'demo-dev')].metadata.labels['foreign/changed'] = 'x'
    elif mutation == 'stale_resource':
        source['source_namespaces']['demo-dev'].metadata.resource_version = '11-stale'
    elif mutation == 'missing_consent':
        source['consent_manifest']['transfer_targets'] = []
    else:
        source['source_related_objects'][('demo-dev', 'RoleBinding', 'foreign')] = {}
    with pytest.raises((ValueError, TypeError, KeyError)):
        inspect_capsule_complete_dry_run_shapes(
            **source,
            preview_objects=previews,
        )


def test_g2g3_trace_requires_start_and_matching_preview_readback_claim():
    source, previews, baseline = _g2_source_case()
    patch = build_capsule_scope_patch_review(**source)
    dryrun = inspect_capsule_complete_dry_run_shapes(**source, preview_objects=previews)
    plan, related = source['plan'], source['related']
    readback = _readback(
        plan,
        related,
        source['current_capsule_cr'],
        source['source_namespaces']['demo-dev'],
        baseline,
    )
    now = datetime.now(UTC)
    started = _audit_start(plan, related, at=now)
    observed = dict(started)
    observed.update(
        {
            'event_type': 'readback_candidate',
            'sequence': 2,
            'event_at': (now + timedelta(seconds=2)).isoformat(),
            'previous_event_sha256': started['event_sha256'],
            'outcome': 'readback_observed',
            'readback_sha256': readback['readback_sha256'],
            'observed_count': readback['observed_count'],
            'pending_count': readback['pending_count'],
            'transferred_count': readback['transferred_count'],
            'ambiguous_count': readback['ambiguous_count'],
        }
    )
    observed['event_sha256'] = _event_checksum(observed)
    rows = [
        {
            'id': 90,
            'actor_user_id': 30,
            'target_type': 'kubernetes_tenant_release_capsule_handoff_execution',
            'target_id': plan['tenant_id'],
            'action': 'tenant.release.capsule_handoff_started',
            'created_at': now + timedelta(seconds=1),
            'metadata_json': started,
        },
        {
            'id': 91,
            'actor_user_id': 30,
            'target_type': 'kubernetes_tenant_release_capsule_handoff_execution',
            'target_id': plan['tenant_id'],
            'action': 'tenant.release.capsule_handoff_readback_candidate',
            'created_at': now + timedelta(seconds=3),
            'metadata_json': observed,
        },
    ]
    result = inspect_capsule_scope_g2g3_trace(
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        rows=rows,
        patch_review=patch,
        preview_review=dryrun,
        readback_candidate=readback,
    )
    assert result['recorded_readback_matches_candidate'] is True
    assert result['status'] == 'incomplete_or_uncertain_g2g3_manual_recovery_required'
    assert result['start_db_commit_verified'] is False
    assert result['provider_execution_admitted'] is False
    assert result['release_authorized'] is False
    with pytest.raises(ValueError):
        inspect_capsule_scope_g2g3_trace(
            plan=plan,
            related=related,
            accepted_actor_user_id=30,
            rows=rows[1:],
            patch_review=patch,
            preview_review=dryrun,
            readback_candidate=readback,
        )
    with pytest.raises(ValueError, match='diverged'):
        inspect_capsule_scope_g2g3_trace(
            plan=plan,
            related=related,
            accepted_actor_user_id=30,
            rows=rows,
            patch_review=patch,
            preview_review={**dryrun, 'scope_items_sha256': '0' * 64},
            readback_candidate=readback,
        )


def _g2_related_case(kind):
    case = _full_related_case(kind, include_foreign=True)
    plan, related, _, cr, namespace, _, evidence, foreign = case
    report = assess_capsule_resource_handoff_scope(plan=plan, related=related)
    now = datetime.now(UTC).isoformat()
    approval = {
        'status': 'acknowledged_pending_provider_handoff',
        'plan_sha256': plan['plan_sha256'],
        'approved_by': 11,
        'requested_by': 10,
        'approved_at': now,
        'provider_handoff_verified': False,
        'release_authorized': False,
    }
    acceptance = {
        'status': 'platform_admin_handoff_accepted',
        'accepted_by': 12,
        'reviewed_by': 11,
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'accepted_at': now,
        'consent_verified': True,
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
    targets = []
    for row in report['resources']:
        if row['inventory_decision'] not in (
            'candidate_kaori_metadata_handoff_review',
            'explicit_kaori_metadata_handoff_review',
        ):
            continue
        labels = (
            ['app.kubernetes.io/managed-by', 'kaori.io/tenant-id']
            if row['kind'] == 'Namespace'
            else next(iter(evidence.values()))['approved_label_keys']
        )
        targets.append(
            {
                'kind': row['kind'],
                'namespace': row['namespace'],
                'name': row['name'],
                'uid': row['uid'],
                'resource_version': row['resource_version'],
                'policy_sha256': row['policy_sha256'],
                'metadata_sha256': row['metadata_sha256'],
                'decision': 'proposed_metadata_labels_only',
                'proposed_label_keys': list(labels),
            }
        )
    manifest = {
        'contract_version': 'capsule-resource-successor-consent/v1',
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': report['worklist_sha256'],
        'resource_review_sha256': report['resource_review_sha256'],
        'change_reference': plan['change_reference'],
        'reviewed_by': 11,
        'accepted_by': 12,
        'accepted_at': now,
        'transfer_targets': targets,
    }
    original = {key: value['before'] for key, value in evidence.items()}
    original[('demo-dev', kind, 'external-control')] = foreign
    params = dict(
        plan=plan,
        related=related,
        current_capsule_cr=cr,
        source_namespaces={'demo-dev': namespace},
        source_related_objects=original,
        approval=approval,
        acceptance=acceptance,
        consent_manifest=manifest,
    )
    ns_preview = deepcopy(namespace)
    ns_preview.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
    del ns_preview.metadata.labels['kaori.io/tenant-id']
    preview = {
        ('', 'Namespace', 'demo-dev'): ns_preview,
        next(iter(evidence)): next(iter(evidence.values()))['current'],
    }
    return params, preview


@pytest.mark.parametrize('kind', ('ResourceQuota', 'LimitRange', 'RoleBinding'))
def test_complete_g2_scope_covers_related_control_and_preserves_foreign(kind):
    source, previews = _g2_related_case(kind)
    prepared = build_capsule_scope_patch_review(**source)
    assert prepared['transfer_candidate_count'] == 2
    assert prepared['preserved_namespaced_count'] == 1
    assert prepared['globally_preserved_count'] == 1
    assert len(prepared['scope_items']) == 5
    assert len([row for row in prepared['scope_items'] if row.get('patch_sha256')]) == 2
    dryrun = inspect_capsule_complete_dry_run_shapes(
        **source,
        preview_objects=previews,
    )
    assert dryrun['preview_count'] == 2
    assert dryrun['server_dry_run_completed'] is False
    assert dryrun['provider_execution_admitted'] is False
    assert dryrun['release_authorized'] is False
    assert 'existing-serviceaccount' not in str(dryrun)


@pytest.mark.parametrize('kind', ('ResourceQuota', 'LimitRange', 'RoleBinding'))
def test_complete_g2_scope_rejects_missing_foreign_control_or_related_dryrun(kind):
    source, previews = _g2_related_case(kind)
    source['source_related_objects'].pop(('demo-dev', kind, 'external-control'))
    with pytest.raises(ValueError, match='every namespaced'):
        build_capsule_scope_patch_review(**source)
    source, previews = _g2_related_case(kind)
    previews.pop(('demo-dev', kind, 'controlled'))
    with pytest.raises(ValueError, match='partial'):
        inspect_capsule_complete_dry_run_shapes(
            **source,
            preview_objects=previews,
        )
    source, previews = _g2_related_case(kind)
    if kind == 'RoleBinding':
        previews[('demo-dev', kind, 'controlled')].subjects[0]['name'] = 'changed'
    else:
        previews[('demo-dev', kind, 'controlled')].spec['forged'] = True
    with pytest.raises(ValueError):
        inspect_capsule_complete_dry_run_shapes(
            **source,
            preview_objects=previews,
        )


def test_complete_g2g3_structural_match_does_not_authenticate_provider_or_authorize_release():
    source, previews, baseline = _g2_source_case()
    prepared = build_capsule_scope_patch_review(**source)
    dryrun = inspect_capsule_complete_dry_run_shapes(
        **source,
        preview_objects=previews,
    )
    plan, related = source['plan'], source['related']
    changed = deepcopy(previews[('', 'Namespace', 'demo-dev')])
    changed.metadata.resource_version = '10'
    readback = _readback(
        plan,
        related,
        source['current_capsule_cr'],
        changed,
        baseline,
    )
    assert readback['pending_count'] == 0
    assert readback['transferred_count'] == 1
    assert readback['blockers'] == [
        'capsule_controller_provenance_unverified',
        'provider_execution_authority_unverified',
    ]
    now = datetime.now(UTC)
    start = _audit_start(plan, related, at=now)
    observed = {
        **start,
        'event_type': 'readback_candidate',
        'sequence': 2,
        'event_at': (now + timedelta(seconds=2)).isoformat(),
        'previous_event_sha256': start['event_sha256'],
        'outcome': 'readback_observed',
        'readback_sha256': readback['readback_sha256'],
        'observed_count': readback['observed_count'],
        'pending_count': readback['pending_count'],
        'transferred_count': readback['transferred_count'],
        'ambiguous_count': readback['ambiguous_count'],
    }
    observed['event_sha256'] = _event_checksum(observed)

    def row(n, action, event, at):
        return {
            'id': n,
            'actor_user_id': 30,
            'target_type': 'kubernetes_tenant_release_capsule_handoff_execution',
            'target_id': plan['tenant_id'],
            'action': action,
            'created_at': at,
            'metadata_json': event,
        }

    rows = [
        row(100, 'tenant.release.capsule_handoff_started', start, now + timedelta(seconds=1)),
        row(101, 'tenant.release.capsule_handoff_readback_candidate', observed, now + timedelta(seconds=3)),
    ]
    trace = inspect_capsule_scope_g2g3_trace(
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        rows=rows,
        patch_review=prepared,
        preview_review=dryrun,
        readback_candidate=readback,
    )
    assert trace['status'] == 'complete_g2g3_claims_correlated_unverified'
    assert trace['all_candidates_structurally_transferred'] is True
    assert trace['recorded_readback_matches_candidate'] is True
    assert trace['start_db_commit_verified'] is False
    assert trace['readback_authoritative_verified'] is False
    assert trace['controller_origin_attested'] is False
    assert trace['provider_handoff_verified'] is False
    assert trace['release_authorized'] is False
    spoofed = dict(readback, blockers=[*readback['blockers'], 'unexpected_policy_drift'])
    with pytest.raises(ValueError):
        inspect_capsule_scope_g2g3_trace(
            plan=plan,
            related=related,
            accepted_actor_user_id=30,
            rows=rows,
            patch_review=prepared,
            preview_review=dryrun,
            readback_candidate=spoofed,
        )


def test_g2_manifest_explicitly_covers_capsule_cr_and_every_global_quota_source():
    source, previews, baseline = _g2_source_case()
    plan, related = source['plan'], source['related']
    shared = [
        {
            'kind': 'GlobalResourceQuota',
            'name': 'shared',
            'uid': 'global-uid',
            'resource_version': '23',
            'scope': 'direct_tenant_selector',
            'policy_sha256': 'a' * 64,
        }
    ]
    quota = related['global_quota']
    quota['resources'] = shared
    quota['count'] = 1
    quota['scope_sha256'] = _digest(
        {
            'api_version': quota['served_version'],
            'resources': shared,
        }
    )
    plan['handoff_components'][0]['capsule_shared_quota_sha256'] = quota['scope_sha256']
    plan['handoff_fingerprint'] = handoff_fingerprint(plan['handoff_components'])
    plan['plan_sha256'] = _plan_hash(plan)
    report = assess_capsule_resource_handoff_scope(plan=plan, related=related)
    source['approval']['plan_sha256'] = plan['plan_sha256']
    source['acceptance']['plan_sha256'] = plan['plan_sha256']
    source['acceptance']['handoff_fingerprint'] = plan['handoff_fingerprint']
    manifest = source['consent_manifest']
    manifest['plan_sha256'] = plan['plan_sha256']
    manifest['handoff_fingerprint'] = plan['handoff_fingerprint']
    manifest['worklist_sha256'] = report['worklist_sha256']
    manifest['resource_review_sha256'] = report['resource_review_sha256']
    prepared = build_capsule_scope_patch_review(**source)
    assert prepared['complete_scope_count'] == 3
    assert len(prepared['scope_items']) == 3
    assert prepared['globally_preserved_count'] == 2
    assert prepared['global_quota_provider_readback_verified'] is False
    entries = {(item['kind'], item['name']): item for item in prepared['scope_items']}
    assert entries[('CapsuleTenant', 'demo')]['operation'] == 'preserve_source_only_unverified'
    assert entries[('GlobalResourceQuota', 'shared')]['operation'] == 'preserve_source_only_unverified'
    assert entries[('GlobalResourceQuota', 'shared')]['policy_sha256'] == 'a' * 64
    assert entries[('GlobalResourceQuota', 'shared')]['source_resource_version'] == '23'
    assert entries[('Namespace', 'demo-dev')]['operation'] == 'conditional_metadata_dry_run_candidate'
    preview = inspect_capsule_complete_dry_run_shapes(**source, preview_objects=previews)
    assert preview['scope_items_sha256'] == prepared['scope_items_sha256']
    assert preview['provider_dry_run_source_authenticated'] is False
    assert preview['release_authorized'] is False


def test_g2_rejects_unresolved_shared_quota_selector_instead_of_omitting_it():
    source, _, _ = _g2_source_case()
    plan, related = source['plan'], source['related']
    quota = related['global_quota']
    quota['resources'] = [
        {
            'kind': 'GlobalResourceQuota',
            'name': 'uncertain',
            'uid': 'other-uid',
            'resource_version': '1',
            'scope': 'unverified_selector',
            'policy_sha256': 'a' * 64,
        }
    ]
    quota['count'] = 1
    quota['scope_sha256'] = _digest(
        {
            'api_version': quota['served_version'],
            'resources': quota['resources'],
        }
    )
    plan['handoff_components'][0]['capsule_shared_quota_sha256'] = quota['scope_sha256']
    plan['handoff_fingerprint'] = handoff_fingerprint(plan['handoff_components'])
    plan['plan_sha256'] = _plan_hash(plan)
    with pytest.raises(ValueError):
        build_capsule_scope_patch_review(**source)


@pytest.mark.parametrize(
    'mutation',
    [
        'drop_capsule_cr',
        'add_unknown_global_quota',
        'turn_preservation_into_patch',
        'replace_cr_resource_version',
        'forge_preserved_policy',
    ],
)
def test_g2g3_trace_rejects_rehashed_tampered_full_preservation_manifest(mutation):
    source, previews, _ = _g2_source_case()
    patch = build_capsule_scope_patch_review(**source)
    changed = deepcopy(patch)
    items = changed['scope_items']
    capsule = next(item for item in items if item['kind'] == 'CapsuleTenant')
    if mutation == 'drop_capsule_cr':
        items.remove(capsule)
    elif mutation == 'add_unknown_global_quota':
        items.append(
            {
                'namespace': '',
                'kind': 'GlobalResourceQuota',
                'name': 'injected',
                'uid': 'foreign',
                'source_resource_version': '1',
                'operation': 'preserve_source_only_unverified',
                'policy_sha256': 'c' * 64,
            }
        )
    elif mutation == 'turn_preservation_into_patch':
        capsule['operation'] = 'conditional_metadata_dry_run_candidate'
        capsule['patch_sha256'] = 'a' * 64
    elif mutation == 'replace_cr_resource_version':
        capsule['source_resource_version'] = 'different-provider-object-version'
    else:
        capsule['policy_sha256'] = 'f' * 64
    changed['scope_items_sha256'] = _digest(items)
    changed['complete_scope_count'] = len(items)
    with pytest.raises(ValueError, match='manifest|provider|preservation'):
        inspect_capsule_scope_g2g3_trace(
            plan=source['plan'],
            related=source['related'],
            accepted_actor_user_id=30,
            rows=[],
            patch_review=changed,
            preview_review={},
            readback_candidate={},
        )


def test_g2_no_global_quota_does_not_claim_live_quota_readback_pass():
    source, previews, _ = _g2_source_case()
    review = build_capsule_scope_patch_review(**source)
    assert review['globally_preserved_count'] == 1
    assert review['scope_items'][0]['kind'] == 'CapsuleTenant'
    assert review['scope_items'][0]['operation'] == 'preserve_source_only_unverified'
    assert review['global_quota_provider_readback_verified'] is False
    assert review['source_provider_authenticated'] is False
    assert review['start_committed'] is False
    assert review['release_authorized'] is False


@pytest.mark.parametrize(
    'attack',
    [
        'lineage_sha_foreign',
        'lineage_origin_self_attested',
        'lineage_status_altered',
        'source_inventory_status_altered',
        'missing_source_quota_posture',
        'malformed_source_findings',
    ],
)
def test_g3_source_rbac_lineage_and_inventory_are_plan_bound(attack):
    plan, related, cr, ns, baseline = _inputs()
    source = deepcopy(related)
    if attack == 'lineage_sha_foreign':
        source['rbac_lineage']['lineage_sha256'] = 'f' * 64
    elif attack == 'lineage_origin_self_attested':
        source['rbac_lineage']['controller_origin_verified'] = True
    elif attack == 'lineage_status_altered':
        source['rbac_lineage']['status'] = 'controller_provenance_verified'
    elif attack == 'source_inventory_status_altered':
        source['status'] = 'verified_provider_snapshot'
    elif attack == 'missing_source_quota_posture':
        source['global_quota'].pop('status')
    else:
        source['blockers'] = 'caller-supplied-string-instead-of-list'
    # Recomputing the related LIST hash does not bind RBAC lineage,
    # collector findings or a changed provider authority status to the plan.
    with pytest.raises(ValueError, match='RBAC lineage or inventory posture'):
        inspect_capsule_readback_candidate(
            plan=plan,
            source_related=source,
            current_related=deepcopy(source),
            current_capsule_cr=cr,
            current_namespaces={'demo-dev': ns},
            namespace_baselines=[baseline],
            tenant_id='tenant-1',
        )


@pytest.mark.parametrize(
    ('area', 'failure'),
    [
        ('related', 'related_inventory_has_unresolved_provider_findings'),
        ('quota', 'global_quota_has_unresolved_provider_findings'),
        ('lineage', 'rbac_lineage_has_unresolved_provider_findings'),
        ('missing_status', 'related_inventory_provenance_or_coverage_unverified'),
        ('missing_blockers', 'related_inventory_provenance_or_coverage_unverified'),
        ('non_string_findings', 'related_inventory_provenance_or_coverage_unverified'),
    ],
)
def test_g3_current_provider_findings_cannot_be_hidden_by_matching_list_hashes(area, failure):
    plan, source, cr, ns, baseline = _inputs()
    current = deepcopy(source)
    if area == 'related':
        current['blockers'].append('Capsule RoleBinding/demo-dev/foreign has conflicting provider ownership.')
    elif area == 'quota':
        current['global_quota']['blockers'].append('GlobalResourceQuota selector is ambiguous.')
    elif area == 'lineage':
        current['rbac_lineage']['blockers'].append(
            'Capsule controller RoleBinding intent has conflicting grant evidence.'
        )
    elif area == 'missing_status':
        current.pop('status')
    elif area == 'missing_blockers':
        current.pop('blockers')
    else:
        current['blockers'].append({'detail': 'untrusted'})
    # No policy, LIST RV or global-quota hash changed; these source
    # observations still must prevent any structurally clean claim.
    review = inspect_capsule_readback_candidate(
        plan=plan,
        source_related=source,
        current_related=current,
        current_capsule_cr=cr,
        current_namespaces={'demo-dev': ns},
        namespace_baselines=[baseline],
        tenant_id='tenant-1',
    )
    assert failure in review['blockers']
    assert review['provider_handoff_verified'] is False
    assert review['auto_retry_authorized'] is False
    assert review['release_authorized'] is False


def test_g3_known_kaori_handoff_warning_not_mistaken_for_foreign_provenance():
    plan, source, current, cr, namespace, baseline, evidence, foreign = _full_related_case(
        'ResourceQuota', include_foreign=True
    )
    warning = (
        'Capsule ResourceQuota/demo-dev/controlled retains KAORI '
        'provider controls requiring separately admitted handoff.'
    )
    source['blockers'] = [warning]
    # The canonical classifier may still report original KAORI controls
    # as pending handoff; no arbitrary warning gets a general exemption.
    receipt = inspect_capsule_readback_candidate(
        plan=plan,
        source_related=source,
        current_related=current,
        current_capsule_cr=cr,
        current_namespaces={'demo-dev': namespace},
        namespace_baselines=[baseline],
        tenant_id=plan['tenant_id'],
        related_transfer_evidence=evidence,
    )
    assert 'related_inventory_has_unresolved_provider_findings' not in receipt['blockers']
    assert 'capsule_controller_provenance_unverified' in receipt['blockers']
    assert receipt['provider_handoff_verified'] is False


def test_g3_transferred_resource_cannot_retain_current_kaori_pending_warning():
    plan, source, current, cr, namespace, baseline, evidence, foreign = _full_related_case(
        'RoleBinding', include_foreign=True
    )
    current['blockers'] = [
        'Capsule RoleBinding/demo-dev/controlled retains KAORI provider controls requiring separately admitted handoff.'
    ]
    readback = inspect_capsule_readback_candidate(
        plan=plan,
        source_related=source,
        current_related=current,
        current_capsule_cr=cr,
        current_namespaces={'demo-dev': namespace},
        namespace_baselines=[baseline],
        tenant_id=plan['tenant_id'],
        related_transfer_evidence=evidence,
    )
    assert readback['related_resource_observations'][0]['state'] == 'provider_markers_transferred'
    assert 'related_current_handoff_finding_contradicts_readback' in readback['blockers']
    assert readback['provider_handoff_verified'] is False
    assert readback['release_authorized'] is False

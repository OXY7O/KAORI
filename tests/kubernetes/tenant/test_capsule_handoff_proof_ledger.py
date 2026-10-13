"""Capsule proof ledger/key pin source regression fixtures — AUTHORED NOT EXECUTED.

No live SQL, Alembic migration, PostgreSQL/SQLite engine, Kubernetes API,
CI/CD/pytest, provider UAT or Release is run under the gate HOLD.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import String

from app.kubernetes.tenant import capsule_handoff_proof_storage_review as store
from app.kubernetes.tenant.capsule_handoff_collector_key_pin import (
    inspect_capsule_collector_key_pin,
)
from app.models.capsule_handoff_proof import (
    CapsuleHandoffAuditBatch,
    CapsuleHandoffResourceConsentRecord,
)

_KEY = b'fixture-collector-key-material-only-not-a-real-secret-32bytes'


def _case():
    captured = datetime.now(UTC) - timedelta(minutes=2)
    accepted = captured + timedelta(minutes=1)
    recorded = datetime.now(UTC) + timedelta(seconds=1)
    report = {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'generation': 7,
        'plan_sha256': 'a' * 64,
        'worklist_sha256': 'b' * 64,
        'resource_review_sha256': 'c' * 64,
        'source_candidate_count': 2,
    }
    collector = {
        'status': 'collector_mac_valid_upstream_apiserver_origin_unverified',
        'collector_mac_verified': True,
        'apiserver_audit_integrity_verified': False,
        'tenant_id': 'tenant-1',
        'plan_sha256': report['plan_sha256'],
        'worklist_sha256': report['worklist_sha256'],
        'resource_review_sha256': report['resource_review_sha256'],
        'batch_id': '00000000-0000-4000-8000-000000000001',
        'collector_id': 'audit-collector-1',
        'key_id': 'operator-pin-1',
        'claims_sha256': 'd' * 64,
        'collector_receipt_sha256': 'e' * 64,
    }
    consent = {
        'consent_source_authenticated': False,
        'independent_consent_record_committed': False,
        'plan_sha256': report['plan_sha256'],
        'worklist_sha256': report['worklist_sha256'],
        'resource_review_sha256': report['resource_review_sha256'],
        'resource_consent_manifest_sha256': 'f' * 64,
        'resource_scope_sha256': '0' * 64,
        'resource_count': 2,
    }
    batch = {
        'id': 91,
        'batch_id': collector['batch_id'],
        'tenant_id': report['tenant_id'],
        'cluster_id': report['cluster_id'],
        'generation': report['generation'],
        'plan_sha256': report['plan_sha256'],
        'worklist_sha256': report['worklist_sha256'],
        'resource_review_sha256': report['resource_review_sha256'],
        'claims_sha256': collector['claims_sha256'],
        'receipt_sha256': collector['collector_receipt_sha256'],
        'collector_id': collector['collector_id'],
        'key_id': collector['key_id'],
        'captured_at': captured,
        'recorded_at': recorded,
    }
    consent_row = {
        'id': 92,
        'tenant_id': report['tenant_id'],
        'batch_id': batch['batch_id'],
        'plan_sha256': report['plan_sha256'],
        'worklist_sha256': report['worklist_sha256'],
        'resource_review_sha256': report['resource_review_sha256'],
        'consent_manifest_sha256': consent['resource_consent_manifest_sha256'],
        'resource_scope_sha256': consent['resource_scope_sha256'],
        'target_count': 2,
        'requester_user_id': 10,
        'reviewer_user_id': 11,
        'successor_user_id': 12,
        'accepted_at': accepted,
        'recorded_at': recorded + timedelta(seconds=1),
    }
    return report, collector, consent, batch, consent_row


def _inspect(report, collector, consent, batches, consents, actors=(10, 11, 12)):
    return store.inspect_capsule_proof_storage(
        resource_report=report,
        collector_receipt_review=collector,
        consent_review=consent,
        requester_user_id=actors[0],
        reviewer_user_id=actors[1],
        successor_user_id=actors[2],
        batch_rows=batches,
        consent_rows=consents,
    )


def test_missing_batch_cannot_be_claimed_committed_or_admitted():
    report, collector, consent, batch, consent_row = _case()
    result = _inspect(report, collector, consent, [], [])
    assert result['status'] == 'no_committed_proof_evidence_observed'
    assert result['database_write_once_guaranteed'] is False
    assert result['append_authorized'] is False
    assert result['provider_execution_admitted'] is False


def test_one_committed_batch_without_consent_is_manual_recovery_only():
    report, collector, consent, batch, consent_row = _case()
    result = _inspect(report, collector, consent, [batch], [])
    assert result['status'] == 'batch_without_committed_consent_requires_manual_review'
    assert result['batch_record_count'] == 1
    assert result['consent_record_count'] == 0
    assert result['release_authorized'] is False


def test_exact_batch_and_consent_records_do_not_prove_external_trust():
    report, collector, consent, batch, consent_row = _case()
    result = _inspect(report, collector, consent, [batch], [consent_row])
    assert result['status'] == 'one_batch_and_consent_record_correlated_unattested'
    assert len(result['batch_record_anchor_sha256']) == 64
    assert len(result['consent_record_anchor_sha256']) == 64
    assert result['historical_replay_absence_proven'] is False
    assert result['apiserver_audit_integrity_verified'] is False
    assert result['independent_consent_authority_verified'] is False
    assert result['resource_specific_handoff_admitted'] is False


@pytest.mark.parametrize(
    'which,field,value',
    [
        ('batch', 'tenant_id', 'foreign-tenant'),
        ('batch', 'batch_id', '00000000-0000-4000-8000-000000000009'),
        ('batch', 'plan_sha256', '1' * 64),
        ('batch', 'resource_review_sha256', '2' * 64),
        ('batch', 'claims_sha256', '3' * 64),
        ('batch', 'key_id', 'unregistered-key'),
        ('consent', 'worklist_sha256', '4' * 64),
        ('consent', 'batch_id', '00000000-0000-4000-8000-000000000044'),
        ('consent', 'target_count', 1),
        ('consent', 'reviewer_user_id', 10),
        ('consent', 'consent_manifest_sha256', '5' * 64),
    ],
)
def test_stale_cross_plan_replay_and_identity_mismatch_fail_closed(which, field, value):
    report, collector, consent, batch, consent_row = _case()
    target = batch if which == 'batch' else consent_row
    target[field] = value
    with pytest.raises(ValueError):
        _inspect(report, collector, consent, [batch], [consent_row])


def test_consent_without_batch_and_duplicates_are_never_silently_filtered():
    report, collector, consent, batch, consent_row = _case()
    with pytest.raises(ValueError):
        _inspect(report, collector, consent, [], [consent_row])
    with pytest.raises(ValueError):
        _inspect(report, collector, consent, [batch, deepcopy(batch)], [])
    with pytest.raises(ValueError):
        _inspect(report, collector, consent, [batch], [consent_row, deepcopy(consent_row)])


def test_broken_commit_chronology_and_actor_independence_fail_closed():
    report, collector, consent, batch, consent_row = _case()
    consent_row['recorded_at'] = batch['recorded_at'] - timedelta(seconds=1)
    with pytest.raises(ValueError):
        _inspect(report, collector, consent, [batch], [consent_row])
    consent_row['recorded_at'] = datetime.now(UTC) + timedelta(seconds=3)
    with pytest.raises(ValueError):
        _inspect(report, collector, consent, [batch], [consent_row], actors=(10, 10, 12))


def test_key_pin_fingerprint_and_active_rotation_window_are_not_authority():
    now = datetime.now(UTC)
    descriptor = {
        'contract_version': 'capsule-collector-key-pin/v1',
        'cluster_id': 'cluster-1',
        'collector_id': 'audit-collector-1',
        'key_id': 'operator-pin-1',
        'key_fingerprint_sha256': hashlib.sha256(_KEY).hexdigest(),
        'issued_at': (now - timedelta(hours=1)).isoformat(),
        'expires_at': (now + timedelta(hours=1)).isoformat(),
        'state': 'active',
    }
    pin = inspect_capsule_collector_key_pin(
        descriptor=descriptor,
        cluster_id='cluster-1',
        collector_id='audit-collector-1',
        key_id='operator-pin-1',
        backend_key_material=_KEY,
        pinned_fingerprint_sha256=descriptor['key_fingerprint_sha256'],
        now=now,
    )
    assert pin['key_material_matches_pin'] is True
    assert pin['backend_trust_store_source_attested'] is False
    assert pin['key_rotation_revocation_enforced'] is False
    assert pin['release_authorized'] is False
    assert _KEY.hex() not in str(pin)
    descriptor['state'] = 'revoked'
    with pytest.raises(ValueError):
        inspect_capsule_collector_key_pin(
            descriptor=descriptor,
            cluster_id='cluster-1',
            collector_id='audit-collector-1',
            key_id='operator-pin-1',
            backend_key_material=_KEY,
            pinned_fingerprint_sha256=descriptor['key_fingerprint_sha256'],
            now=now,
        )


def test_key_pin_rejects_wrong_runtime_material_and_foreign_cluster():
    now = datetime.now(UTC)
    descriptor = {
        'contract_version': 'capsule-collector-key-pin/v1',
        'cluster_id': 'cluster-1',
        'collector_id': 'audit-collector-1',
        'key_id': 'operator-pin-1',
        'key_fingerprint_sha256': hashlib.sha256(_KEY).hexdigest(),
        'issued_at': (now - timedelta(minutes=1)).isoformat(),
        'expires_at': (now + timedelta(minutes=1)).isoformat(),
        'state': 'active',
    }
    kwargs = dict(
        descriptor=descriptor,
        cluster_id='cluster-1',
        collector_id='audit-collector-1',
        key_id='operator-pin-1',
        pinned_fingerprint_sha256=descriptor['key_fingerprint_sha256'],
        now=now,
    )
    with pytest.raises(ValueError):
        inspect_capsule_collector_key_pin(
            **kwargs,
            backend_key_material=b'other-trust-material-longer-than-32-bytes',
        )
    with pytest.raises(ValueError):
        inspect_capsule_collector_key_pin(
            **{**kwargs, 'cluster_id': 'foreign-cluster'},
            backend_key_material=_KEY,
        )


def test_models_register_exact_composite_fk_and_sqlalchemy_string_type_first():
    batch_t = CapsuleHandoffAuditBatch.__table__
    consent_t = CapsuleHandoffResourceConsentRecord.__table__
    assert isinstance(batch_t.c.tenant_id.type, String)
    assert batch_t.c.tenant_id.type.length == 36
    assert isinstance(consent_t.c.tenant_id.type, String)
    composite = [
        constraint
        for constraint in consent_t.foreign_key_constraints
        if constraint.name == 'fk_capsule_resource_consent_exact_audit_batch'
    ]
    assert len(composite) == 1
    assert len(composite[0].elements) == 5
    assert {elem.target_fullname for elem in composite[0].elements} == {
        'capsule_handoff_audit_batches.batch_id',
        'capsule_handoff_audit_batches.tenant_id',
        'capsule_handoff_audit_batches.plan_sha256',
        'capsule_handoff_audit_batches.worklist_sha256',
        'capsule_handoff_audit_batches.resource_review_sha256',
    }


def test_migration_contains_write_once_guards_antireplay_and_safe_downgrade():
    migration = Path('migrations/versions/20261011_capsule_audit_consent_proof_ledger.py').read_text()
    assert "down_revision = '20261011_capsule_ledger'" in migration
    assert 'uq_capsule_audit_batch_plan_once' in migration
    assert 'uq_capsule_resource_consent_plan_once' in migration
    assert 'fk_capsule_resource_consent_exact_audit_batch' in migration
    assert "((_BATCH, 'batch'), (_CONSENT, 'consent'))" in migration
    assert "f'tr_capsule_{prefix}_deny_{operation}'" in migration
    assert "'TRUNCATE'" in migration
    assert 'PRAGMA foreign_keys' in migration
    assert 'Refusing to destroy committed Capsule audit/consent evidence.' in migration


def test_read_only_tenant_scan_never_filters_to_latest_plan(monkeypatch):
    report, collector, consent, batch, consent_row = _case()

    class Col:
        def asc(self):
            return 'id asc'

    class Query:
        def __init__(self, rows):
            self.rows = rows
            self.calls = []

        def filter_by(self, **kwargs):
            self.calls.append(('filter', kwargs))
            return self

        def order_by(self, _order):
            self.calls.append(('sort', None))
            return self

        def limit(self, count):
            self.calls.append(('limit', count))
            return self

        def all(self):
            return self.rows

    qb, qc = Query([batch]), Query([consent_row])
    monkeypatch.setattr(store, 'CapsuleHandoffAuditBatch', SimpleNamespace(query=qb, id=Col()))
    monkeypatch.setattr(store, 'CapsuleHandoffResourceConsentRecord', SimpleNamespace(query=qc, id=Col()))
    result = store.read_capsule_proof_history(
        tenant_id='tenant-1',
        resource_report=report,
        collector_receipt_review=collector,
        consent_review=consent,
        requester_user_id=10,
        reviewer_user_id=11,
        successor_user_id=12,
    )
    assert result['append_authorized'] is False
    assert ('filter', {'tenant_id': 'tenant-1'}) in qb.calls
    assert ('filter', {'tenant_id': 'tenant-1'}) in qc.calls
    assert ('limit', 2) in qb.calls
    assert ('limit', 2) in qc.calls
    assert len(qb.calls) == len(qc.calls) == 3

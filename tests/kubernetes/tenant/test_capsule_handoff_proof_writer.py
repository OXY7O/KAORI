"""Authored-only Capsule proof writer source regression fixtures (#1229).

DO NOT run test suite, migration, SQL writes, Kubernetes API or CI/CD while
review branch gates are HOLD.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.kubernetes.tenant import capsule_handoff_proof_writer as writer


def _request():
    return {
        'tenant_id': 'tenant-1', 'actor_user_id': 12,
        'expected_plan_sha256': 'a' * 64,
        'claims': [], 'collector_receipt': {},
        'consent_manifest': {},
        'trusted_collector_id': 'collector-1', 'trusted_key_id': 'pin-1',
        'trusted_hmac_key': b'authored-test-only-material-longer-than-32-bytes',
        'explicit_operator_confirmation': True,
    }


def test_proof_writer_is_disabled_before_any_session_or_authentication():
    assert writer._CAPSULE_PROOF_WRITER_ENABLED is False
    assert writer._AUTHENTICATED_PROVENANCE_AND_CONSENT_WRITER_ENABLED is False
    with patch.object(writer, 'db') as db:
        with patch.object(writer, 'require_platform_admin_actor') as actor:
            with pytest.raises(PermissionError, match='source-staged only'):
                writer.commit_capsule_proof_pair_staged(**_request())
            db.session.assert_not_called()
            actor.assert_not_called()


@pytest.mark.parametrize('proof_enabled,origin_enabled', [
    (False, False), (True, False), (False, True),
])
def test_no_individual_feature_gate_or_forged_confirmation_can_write(
    monkeypatch, proof_enabled, origin_enabled,
):
    monkeypatch.setattr(writer, '_CAPSULE_PROOF_WRITER_ENABLED', proof_enabled)
    monkeypatch.setattr(
        writer, '_AUTHENTICATED_PROVENANCE_AND_CONSENT_WRITER_ENABLED',
        origin_enabled,
    )
    with patch.object(writer, 'db') as db:
        with pytest.raises(PermissionError):
            writer.commit_capsule_proof_pair_staged(**_request())
        db.session.assert_not_called()


def _candidate_fixture(monkeypatch):
    now = datetime.now(UTC).isoformat()
    report = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1',
        'generation': 7, 'plan_sha256': 'a' * 64,
        'worklist_sha256': 'b' * 64,
        'resource_review_sha256': 'c' * 64, 'source_candidate_count': 2,
    }
    collector = {
        'batch_id': '00000000-0000-4000-8000-000000000001',
        'tenant_id': 'tenant-1', 'plan_sha256': report['plan_sha256'],
        'collector_id': 'collector-1', 'key_id': 'pin-1',
        'claims_sha256': 'd' * 64, 'collector_receipt_sha256': 'e' * 64,
    }
    consent = {
        'resource_count': 2, 'resource_consent_manifest_sha256': 'f' * 64,
        'resource_scope_sha256': '1' * 64,
    }
    docket = {
        'review_docket_sha256': '2' * 64,
        'candidate_count': 2,
        'collector_receipt_sha256': collector['collector_receipt_sha256'],
        'resource_consent_manifest_sha256': consent['resource_consent_manifest_sha256'],
    }
    monkeypatch.setattr(writer, 'assess_capsule_resource_handoff_scope', lambda **k: report)
    monkeypatch.setattr(writer, 'review_capsule_origin_consent_docket', lambda **k: docket)
    monkeypatch.setattr(writer, 'inspect_capsule_collector_receipt', lambda **k: collector)
    monkeypatch.setattr(writer, 'inspect_capsule_resource_consent', lambda **k: consent)
    args = {
        'plan': {
            'tenant_id': 'tenant-1', 'generation': 7, 'requested_by': 10,
        },
        'related': {}, 'approval': {'approved_by': 11},
        'acceptance': {'accepted_by': 12},
        'claims': [], 'collector_receipt': {'captured_at': now},
        'consent_manifest': {'accepted_at': now},
        'trusted_collector_id': 'collector-1', 'trusted_key_id': 'pin-1',
        'trusted_hmac_key': _request()['trusted_hmac_key'],
    }
    return args, report, collector, consent, docket


def test_pure_pair_contains_exact_batch_and_consent_fk_without_secrets(monkeypatch):
    args, report, collector, consent, _ = _candidate_fixture(monkeypatch)
    result = writer.build_capsule_proof_pair_candidate(**args)
    batch = result['batch_values']
    record = result['consent_values']
    assert result['status'] == 'proof_insert_pair_candidate_unadmitted'
    assert batch['batch_id'] == record['batch_id']
    for field in ('tenant_id', 'plan_sha256', 'worklist_sha256', 'resource_review_sha256'):
        assert batch[field] == record[field]
    assert batch['generation'] == report['generation']
    assert (
        record['requester_user_id'], record['reviewer_user_id'],
        record['successor_user_id'],
    ) == (10, 11, 12)
    assert record['target_count'] == 2
    assert result['append_authorized'] is False
    assert result['human_consent_authenticated'] is False
    assert result['provider_execution_admitted'] is False
    assert 'trusted_hmac_key' not in str(result)
    assert args['trusted_hmac_key'].hex() not in str(result)


@pytest.mark.parametrize('mutate', [
    lambda a: a['plan'].update(generation=0),
    lambda a: a['plan'].update(requested_by=12),
    lambda a: a['acceptance'].update(accepted_by=10),
    lambda a: a['collector_receipt'].update(captured_at='without-tz'),
    lambda a: a['consent_manifest'].update(accepted_at='without-tz'),
])
def test_pair_rejects_invalid_generation_actors_or_timestamps(monkeypatch, mutate):
    args, *_ = _candidate_fixture(monkeypatch)
    mutate(args)
    with pytest.raises(ValueError):
        writer.build_capsule_proof_pair_candidate(**args)


def test_pair_rejects_cross_source_digest_and_incomplete_candidate_count(monkeypatch):
    args, report, collector, consent, docket = _candidate_fixture(monkeypatch)
    consent['resource_count'] = 1
    with pytest.raises(ValueError):
        writer.build_capsule_proof_pair_candidate(**args)
    consent['resource_count'] = 2
    docket['collector_receipt_sha256'] = '9' * 64
    with pytest.raises(ValueError):
        writer.build_capsule_proof_pair_candidate(**args)


def _triggers():
    return [
        (table, trigger, 'O')
        for table, names in writer._TABLE_GUARDS.items()
        for trigger in names
    ]


def _permissions():
    return [
        {
            'table_name': table, 'may_select': True, 'may_insert': True,
            'may_update': False, 'may_delete': False,
            'may_truncate': False, 'is_owner': False,
            'member_of_owner': False, 'may_create': False,
        }
        for table in writer._TABLE_GUARDS
    ]


def _settings():
    return {
        'fsync': 'on', 'synchronous_commit': 'on',
        'replication_role': 'origin', 'elevated': False,
    }


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def scalars(self):
        return self

    def mappings(self):
        return self

    def one(self):
        return self.rows


class _ReadOnlyPgCatalog:
    """Fake SELECT results, not a DB or live connection."""

    def __init__(self, *, triggers=None, constraints=None, permissions=None, settings=None):
        self.triggers = _triggers() if triggers is None else triggers
        self.constraints = writer._REQUIRED_CONSTRAINTS if constraints is None else constraints
        self.permissions = _permissions() if permissions is None else permissions
        self.settings = _settings() if settings is None else settings
        self.calls = []

    def execute(self, query):
        sql = str(query)
        assert 'INSERT ' not in sql and 'UPDATE ' not in sql and 'DELETE ' not in sql
        self.calls.append(sql)
        if 'FROM pg_trigger' in sql:
            return _Result(self.triggers)
        if 'FROM pg_constraint' in sql:
            return _Result([(name, True) for name in self.constraints])
        if 'FROM pg_class' in sql:
            return _Result(self.permissions)
        if "current_setting('fsync')" in sql:
            return _Result(self.settings)
        raise AssertionError('Unexpected PostgreSQL schema query')


def test_staged_postgres_guard_requires_every_schema_and_role_check():
    source = _ReadOnlyPgCatalog()
    writer._require_postgres_proof_storage_guards(source)
    assert len(source.calls) == 4


@pytest.mark.parametrize('missing', [
    'tr_capsule_batch_deny_update', 'tr_capsule_batch_deny_delete',
    'tr_capsule_batch_deny_truncate',
    'tr_capsule_consent_deny_update', 'tr_capsule_consent_deny_delete',
    'tr_capsule_consent_deny_truncate',
])
def test_staged_postgres_guard_refuses_missing_or_disabled_trigger(missing):
    with pytest.raises(ValueError, match='missing or disabled'):
        writer._require_postgres_proof_storage_guards(_ReadOnlyPgCatalog(
            triggers=[row for row in _triggers() if row[1] != missing],
        ))
    with pytest.raises(ValueError, match='missing or disabled'):
        writer._require_postgres_proof_storage_guards(_ReadOnlyPgCatalog(
            triggers=[(t, name, 'D' if name == missing else state)
                      for t, name, state in _triggers()],
        ))


def test_staged_postgres_guard_refuses_missing_composite_scope_constraint():
    with pytest.raises(ValueError, match='constraints are absent or invalid'):
        writer._require_postgres_proof_storage_guards(_ReadOnlyPgCatalog(
            constraints=set(writer._REQUIRED_CONSTRAINTS)
            - {'fk_capsule_resource_consent_exact_audit_batch'},
        ))


@pytest.mark.parametrize('field,value', [
    ('may_select', False), ('may_insert', False), ('may_update', True),
    ('may_delete', True), ('may_truncate', True), ('is_owner', True),
    ('member_of_owner', True), ('may_create', True),
])
def test_staged_postgres_guard_refuses_privileged_or_incomplete_role(field, value):
    data = _permissions()
    data[0][field] = value
    with pytest.raises(ValueError, match='restricted INSERT-only'):
        writer._require_postgres_proof_storage_guards(_ReadOnlyPgCatalog(
            permissions=data,
        ))


@pytest.mark.parametrize('field,value', [
    ('fsync', 'off'), ('synchronous_commit', 'off'),
    ('replication_role', 'replica'), ('elevated', True),
])
def test_staged_postgres_guard_refuses_nondurable_database_session(field, value):
    settings = _settings()
    settings[field] = value
    with pytest.raises(ValueError, match='WAL, replication or role'):
        writer._require_postgres_proof_storage_guards(_ReadOnlyPgCatalog(
            settings=settings,
        ))


def test_readback_comparison_checks_exact_committed_fields():
    expected = {
        'tenant_id': 'tenant-1', 'plan_sha256': 'a' * 64,
        'batch_id': '00000000-0000-4000-8000-000000000001',
    }
    row = SimpleNamespace(**expected)
    assert writer._stored_matches(row, expected) is True
    assert writer._stored_matches(None, expected) is False
    assert writer._stored_matches(row, {**expected, 'batch_id': 'replayed'}) is False


def test_proof_batch_global_and_tenant_uniqueness_stays_in_model_and_migration():
    from pathlib import Path

    from app.models.capsule_handoff_proof import (
        CapsuleHandoffAuditBatch, CapsuleHandoffResourceConsentRecord,
    )

    batch_uniques = {
        constraint.name for constraint in CapsuleHandoffAuditBatch.__table__.constraints
        if getattr(constraint, 'name', None)
    }
    consent_uniques = {
        constraint.name for constraint in CapsuleHandoffResourceConsentRecord.__table__.constraints
        if getattr(constraint, 'name', None)
    }
    assert 'uq_capsule_audit_batch_global_id' in batch_uniques
    assert 'uq_capsule_audit_batch_tenant_once' in batch_uniques
    assert 'uq_capsule_resource_consent_tenant_once' in consent_uniques
    migration = Path('migrations/versions/20261011_capsule_audit_consent_proof_ledger.py').read_text()
    for name in (
        'uq_capsule_audit_batch_global_id',
        'uq_capsule_audit_batch_tenant_once',
        'uq_capsule_resource_consent_tenant_once',
    ):
        assert name in migration


def test_staged_writer_mentions_legacy_and_prior_start_checks_before_insert():
    from pathlib import Path

    source = Path('app/kubernetes/tenant/capsule_handoff_proof_writer.py').read_text()
    assert "select(CapsuleHandoffLedgerEvent.id)" in source
    assert "kubernetes_tenant_release_capsule_handoff_execution" in source
    assert source.index('Prior Capsule START/legacy execution') < source.index('session.add(CapsuleHandoffAuditBatch')
    assert source.index('session.add(CapsuleHandoffAuditBatch') < source.index('session.add(CapsuleHandoffResourceConsentRecord')
    assert 'with session.begin()' in source

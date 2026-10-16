"""Authored-only Capsule write-once ledger / migration regression contracts #1229.

Do NOT run migration, pytest, CI/CD, provider calls or live SQL under HOLD.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import capsule_handoff_ledger_review as ledger
from app.kubernetes.tenant.capsule_handoff_attempt_state import _event_checksum
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest, capsule_related_scope_sha256
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint


def _scope():
    lists = [
        {'namespace': 'demo-dev', 'kind': kind, 'list_resource_version': 'list-rv', 'count': 0}
        for kind in ('LimitRange', 'ResourceQuota', 'RoleBinding')
    ]
    related_sha = capsule_related_scope_sha256(resources=[], list_snapshots=lists)
    global_quota = {
        'served_version': 'v1beta2',
        'list_resource_version': 'global-rv',
        'resources': [],
        'count': 0,
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
            'capsule_spec_sha256': 'a' * 64,
            'capsule_related_resources_sha256': related_sha,
            'capsule_related_resources_count': '0',
            'capsule_shared_quota_sha256': global_quota['scope_sha256'],
            'capsule_rbac_lineage_sha256': 'b' * 64,
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
    plan = {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'generation': 1,
        'provider': 'capsule',
        'requested_by': 10,
        'requested_at': datetime.now(UTC).isoformat(),
        'handoff_fingerprint': handoff_fingerprint(components),
        'provider_identity': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '3'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid', 'resource_version': '9'},
        ],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-1011',
        'handoff_components': components,
    }
    plan['plan_sha256'] = _plan_hash(plan)
    related = {
        'status': 'read_only_related_inventory',
        'resources': [],
        'resource_count': 0,
        'list_snapshots': lists,
        'resource_sha256': related_sha,
        'global_quota': global_quota,
    }
    return plan, related


def _event(plan, related, *, event_type='started', prior=None, seconds=0):
    actor = 31 if event_type == 'recovery_reviewed' else 30
    worklist = build_capsule_handoff_worklist(plan=plan, related=related)
    count = sum(
        item['decision']
        in (
            'candidate_kaori_metadata_handoff_review',
            'explicit_kaori_metadata_handoff_review',
        )
        for item in worklist['items']
    )
    when = datetime.now(UTC) - timedelta(seconds=30 - seconds)
    event = {
        'contract_version': 'capsule-handoff-attempt/v1',
        'event_type': event_type,
        'attempt_id': '00000000-0000-4000-8000-000000000001',
        'sequence': prior['sequence'] + 1 if prior else 1,
        'event_at': when.isoformat(),
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': worklist['inventory_sha256'],
        'actor_user_id': actor,
        'previous_event_sha256': prior['event_sha256'] if prior else None,
        'event_sha256': None,
        'outcome': {
            'started': 'unknown',
            'partial': 'unknown',
            'readback_candidate': 'readback_observed',
            'recovery_reviewed': 'review_only',
        }[event_type],
        'readback_sha256': None,
        'expected_count': count,
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
    if event_type == 'readback_candidate':
        event.update(
            readback_sha256='e' * 64,
            observed_count=count,
            pending_count=count,
        )
    if event_type == 'recovery_reviewed' and prior is not None:
        for key in (
            'readback_sha256',
            'observed_count',
            'pending_count',
            'transferred_count',
            'ambiguous_count',
        ):
            event[key] = prior[key]
    event['event_sha256'] = _event_checksum(event)
    return event


def _row(event, *, row_id):
    return {
        'id': row_id,
        'event_json': deepcopy(event),
        'event_at': datetime.fromisoformat(event['event_at']),
        'recorded_at': datetime.now(UTC),
        **{name: event[name] for name in ledger._COLUMNS},
    }


def _inspect(plan, related, rows):
    return ledger.inspect_capsule_ledger_rows(
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
        rows=rows,
    )


def test_empty_ledger_never_authorizes_first_attempt():
    plan, related = _scope()
    result = _inspect(plan, related, [])
    assert result['ledger_record_count'] == 0
    assert result['status'] == 'no_attempt_observed_not_authorized'
    assert result['database_schema_applied_verified'] is False
    assert result['append_authorized'] is False
    assert result['provider_execution_admitted'] is False


def test_started_and_partial_ledger_require_independent_recovery():
    plan, related = _scope()
    start = _event(plan, related)
    first = _inspect(plan, related, [_row(start, row_id=10)])
    assert first['status'] == 'started_outcome_unknown_recovery_required'
    partial = _event(plan, related, event_type='partial', prior=start, seconds=3)
    second = _inspect(
        plan,
        related,
        [
            _row(start, row_id=10),
            _row(partial, row_id=11),
        ],
    )
    assert second['status'] == 'partial_handoff_recovery_required'
    assert second['db_write_once_triggers_verified'] is False
    assert second['auto_retry_authorized'] is False
    assert second['release_authorized'] is False


def test_reviewed_readback_claim_is_not_verified_provider_handoff():
    plan, related = _scope()
    start = _event(plan, related)
    candidate = _event(
        plan,
        related,
        event_type='readback_candidate',
        prior=start,
        seconds=3,
    )
    review = _event(
        plan,
        related,
        event_type='recovery_reviewed',
        prior=candidate,
        seconds=6,
    )
    state = _inspect(
        plan,
        related,
        [
            _row(start, row_id=15),
            _row(candidate, row_id=16),
            _row(review, row_id=17),
        ],
    )
    assert state['status'] == 'manual_review_recorded_no_retry_granted'
    assert state['ledger_record_count'] == 3
    assert state['provider_handoff_verified'] is False
    assert state['provider_readback_authoritative_verified'] is False
    assert state['transactional_start_commit_verified'] is False


@pytest.mark.parametrize(
    'corruption',
    [
        lambda r: r.update(plan_sha256='f' * 64),
        lambda r: r.update(sequence=9),
        lambda r: r.update(event_sha256='0' * 64),
        lambda r: r.update(actor_user_id=29),
        lambda r: r.update(attempt_id='00000000-0000-4000-8000-000000000009'),
        lambda r: r.update(event_at=datetime.now(UTC) + timedelta(days=1)),
        lambda r: r.update(recorded_at=None),
        lambda r: r.update(event_json={'secret': 'not-a-valid-event'}),
    ],
)
def test_indexed_columns_payload_or_event_time_drift_fail_closed(corruption):
    plan, related = _scope()
    row = _row(_event(plan, related), row_id=50)
    corruption(row)
    with pytest.raises((ValueError, TypeError)):
        _inspect(plan, related, [row])


def test_out_of_order_duplicate_and_overlong_histories_are_blocked():
    plan, related = _scope()
    start = _event(plan, related)
    row = _row(start, row_id=50)
    with pytest.raises(ValueError):
        _inspect(plan, related, [row, deepcopy(row)])
    with pytest.raises(ValueError):
        _inspect(plan, related, [dict(row, id=51), row])
    with pytest.raises(ValueError):
        _inspect(plan, related, [dict(row, id=i) for i in range(4)])


def test_sql_reader_is_only_bounded_select_not_a_writer(monkeypatch):
    plan, related = _scope()

    class Column:
        def asc(self):
            return 'id ascending'

    class Query:
        def __init__(self):
            self.called = []

        def filter_by(self, **kwargs):
            self.called.append(('filter_by', kwargs))
            return self

        def order_by(self, value):
            self.called.append(('order_by', value))
            return self

        def limit(self, amount):
            self.called.append(('limit', amount))
            return self

        def all(self):
            return []

    query = Query()
    monkeypatch.setattr(
        ledger,
        'CapsuleHandoffLedgerEvent',
        SimpleNamespace(query=query, id=Column()),
    )
    result = ledger.read_capsule_ledger_history(
        tenant_id='tenant-1',
        plan=plan,
        related=related,
        accepted_actor_user_id=30,
    )
    assert result['append_authorized'] is False
    assert ('filter_by', {'tenant_id': 'tenant-1'}) in query.called
    assert ('limit', 4) in query.called
    assert len(query.called) == 3


def test_migration_source_has_write_once_triggers_fencing_and_no_data_drop():
    source = Path('migrations/versions/20261011_capsule_handoff_write_once_ledger.py').read_text()
    assert "down_revision = '20261009_tenant_released'" in source
    assert 'FOR UPDATE' in source  # PostgreSQL Tenant-scope write lock
    assert 'tr_capsule_ledger_deny_update' in source
    assert 'tr_capsule_ledger_deny_delete' in source
    assert 'tr_capsule_ledger_deny_truncate' in source
    assert 'uq_capsule_ledger_tenant_sequence' in source
    assert 'RAISE(ABORT' in source  # SQLite write-once
    assert 'Cannot drop a Capsule handoff ledger containing evidence.' in source


def test_capsule_ledger_model_declares_tenant_type_before_foreign_key():
    """Import/mapping regression for SQLAlchemy 2 mapped_column SchemaItem order."""
    from sqlalchemy import String

    from app.models.capsule_handoff_ledger import CapsuleHandoffLedgerEvent

    tenant_column = CapsuleHandoffLedgerEvent.__table__.c.tenant_id
    assert isinstance(tenant_column.type, String)
    assert tenant_column.type.length == 36
    assert tenant_column.nullable is False
    assert len(tenant_column.foreign_keys) == 1
    foreign_key = next(iter(tenant_column.foreign_keys))
    assert foreign_key.target_fullname == 'tenants.id'
    assert foreign_key.ondelete == 'RESTRICT'

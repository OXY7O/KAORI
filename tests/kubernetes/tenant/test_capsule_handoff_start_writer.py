"""Capsule START writer safety and pre-write fencing (authored only, not run).

No database migration, SQL writes, provider API calls, or CI/CD are executed
while source integration into the DevContainer review branch is held.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.kubernetes.tenant.capsule_handoff_attempt_state import _event_checksum
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest, capsule_related_scope_sha256
from app.kubernetes.tenant.capsule_handoff_start_writer import (
    _CAPSULE_START_WRITER_ENABLED,
    _require_postgres_ledger_write_once_guards,
    build_capsule_start_candidate,
    commit_capsule_start_staged,
)
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint


def _scope():
    lists = [
        {'namespace': 'demo-dev', 'kind': kind, 'list_resource_version': 'rv-list-1', 'count': 0}
        for kind in ('LimitRange', 'ResourceQuota', 'RoleBinding')
    ]
    related_sha = capsule_related_scope_sha256(resources=[], list_snapshots=lists)
    shared = {
        'served_version': 'v1beta2',
        'list_resource_version': 'grq-list-rv',
        'resources': [],
        'count': 0,
    }
    shared['scope_sha256'] = _digest(
        {
            'api_version': 'v1beta2',
            'resources': [],
        }
    )
    components = [
        {
            'kind': 'CapsuleTenant',
            'name': 'kaori-demo',
            'uid': 'cr-uid',
            'resource_version': '3',
            'authority': 'capsule',
            'ownership': 'external_or_unattributed',
            'handoff': 'external_acceptance_required',
            'capsule_spec_sha256': 'a' * 64,
            'capsule_related_resources_sha256': related_sha,
            'capsule_related_resources_count': '0',
            'capsule_shared_quota_sha256': shared['scope_sha256'],
            'capsule_rbac_lineage_sha256': 'b' * 64,
        },
        {
            'kind': 'Namespace',
            'name': 'demo-dev',
            'namespace': 'demo-dev',
            'uid': 'namespace-uid',
            'resource_version': '19',
            'authority': 'capsule',
            'ownership': 'kaori_marker_correlated',
            'handoff': 'external_acceptance_required',
        },
    ]
    plan = {
        'tenant_id': 'tenant-id',
        'cluster_id': 'cluster-id',
        'generation': 1,
        'provider': 'capsule',
        'requested_by': 10,
        'requested_at': datetime.now(UTC).isoformat(),
        'provider_identity': [
            {'kind': 'CapsuleTenant', 'name': 'kaori-demo', 'uid': 'cr-uid', 'resource_version': '3'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'namespace-uid', 'resource_version': '19'},
        ],
        'handoff_components': components,
        'handoff_fingerprint': handoff_fingerprint(components),
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-20261011',
    }
    plan['plan_sha256'] = _plan_hash(plan)
    related = {
        'resources': [],
        'resource_count': 0,
        'list_snapshots': lists,
        'resource_sha256': related_sha,
        'global_quota': shared,
    }
    return plan, related


def _candidate(plan, related, *, attempt_id='00000000-0000-4000-8000-000000000001'):
    return build_capsule_start_candidate(
        tenant_id='tenant-id',
        actor_user_id=30,
        plan=plan,
        related=related,
        attempt_id=attempt_id,
        event_at=datetime.now(UTC),
    )


def test_start_candidate_has_exact_canonical_scope_and_no_credentials_or_provider_bodies():
    plan, related = _scope()
    event = _candidate(plan, related)
    assert event['event_type'] == 'started'
    assert event['sequence'] == 1
    assert event['expected_count'] == 1
    assert event['previous_event_sha256'] is None
    assert event['event_sha256'] == _event_checksum(event)
    assert event['readback_sha256'] is None
    assert event['provider_handoff_verified'] is False
    assert event['release_authorized'] is False
    assert event['secret_material_persisted'] is False
    for forbidden in ('provider_username', 'X509SHA256=', 'role_binding_subjects', 'raw_spec'):
        assert forbidden not in str(event)


@pytest.mark.parametrize(
    'change',
    [
        lambda p, r: p.update(plan_sha256='f' * 64),
        lambda p, r: p.update(tenant_id='other-tenant'),
        lambda p, r: p.update(provider='native_kubernetes'),
        lambda p, r: p['handoff_components'][1].update(uid='rotated'),
        lambda p, r: r.update(resource_sha256='bad'),
        lambda p, r: r['list_snapshots'][0].update(list_resource_version='new-rv'),
        lambda p, r: r['global_quota'].update(scope_sha256='f' * 64),
    ],
)
def test_changed_plan_or_inventory_cannot_produce_a_valid_start(change):
    plan, related = _scope()
    change(plan, related)
    with pytest.raises((TypeError, ValueError, KeyError)):
        _candidate(plan, related)


@pytest.mark.parametrize(
    'attempt_id',
    [
        '',
        'not-a-uuid',
        '00000000-0000-4000-8000-000000000001X',
        'abcdefab-cdef-4abc-8abc-abcdefabcdef'.upper(),
    ],
)
def test_invalid_attempt_identity_is_rejected_by_event_projection(attempt_id):
    plan, related = _scope()
    with pytest.raises(ValueError):
        _candidate(plan, related, attempt_id=attempt_id)


def test_write_is_statically_disabled_before_any_auth_or_sql_session():
    plan, _ = _scope()
    assert _CAPSULE_START_WRITER_ENABLED is False
    with patch('app.kubernetes.tenant.capsule_handoff_start_writer.db') as database:
        with patch('app.kubernetes.tenant.capsule_handoff_start_writer.require_platform_admin_actor') as auth:
            with pytest.raises(PermissionError, match='source-staged only'):
                commit_capsule_start_staged(
                    tenant_id='tenant-id',
                    actor_user_id=30,
                    expected_plan_sha256=plan['plan_sha256'],
                    preflight={},
                    provider_authority={},
                    explicit_operator_confirmation=True,
                )
            database.session.assert_not_called()
            auth.assert_not_called()


def test_confirmed_or_unconfirmed_input_cannot_turn_on_the_writer():
    plan, _ = _scope()
    for confirmed in (False, True):
        with pytest.raises(PermissionError):
            commit_capsule_start_staged(
                tenant_id='tenant-id',
                actor_user_id=30,
                expected_plan_sha256=plan['plan_sha256'],
                preflight={},
                provider_authority={},
                explicit_operator_confirmation=confirmed,
            )


def test_current_admission_always_denies_execution_even_if_writer_gate_changed(monkeypatch):
    from app.kubernetes.tenant import capsule_handoff_start_writer as module

    plan, _ = _scope()
    monkeypatch.setattr(module, '_CAPSULE_START_WRITER_ENABLED', True)
    # No route, DB migration, provider SSR/SAR or full source admission are
    # available. A forged caller cannot get past ordinary argument guards.
    with pytest.raises(ValueError, match='authenticated Capsule START request'):
        module.commit_capsule_start_staged(
            tenant_id='tenant-id',
            actor_user_id=30,
            expected_plan_sha256=plan['plan_sha256'],
            preflight={},
            provider_authority={},
            explicit_operator_confirmation=False,
        )


class _QueryResult:
    def __init__(self, value):
        self.value = value

    def all(self):
        return self.value

    def mappings(self):
        return self

    def one(self):
        return self.value


class _PostgresReviewSession:
    def __init__(self, triggers, state):
        self.triggers = triggers
        self.state = state
        self.calls = 0

    def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return _QueryResult(self.triggers)
        return _QueryResult(self.state)


def _postgres_state():
    return {
        'fsync_setting': 'on',
        'sync_commit': 'on',
        'replication_role': 'origin',
        'elevated': False,
        'is_owner': False,
        'member_of_owner': False,
        'may_insert': True,
        'may_update': False,
        'may_delete': False,
        'may_truncate': False,
    }


def _postgres_triggers():
    return [
        (name, 'O')
        for name in (
            'tr_capsule_ledger_guard_insert',
            'tr_capsule_ledger_deny_update',
            'tr_capsule_ledger_deny_delete',
            'tr_capsule_ledger_deny_truncate',
        )
    ]


def test_staged_db_guard_requires_all_triggers_without_sql_write():
    session = _PostgresReviewSession(_postgres_triggers(), _postgres_state())
    _require_postgres_ledger_write_once_guards(session)
    assert session.calls == 2


@pytest.mark.parametrize(
    'missing',
    [
        'tr_capsule_ledger_guard_insert',
        'tr_capsule_ledger_deny_update',
        'tr_capsule_ledger_deny_delete',
        'tr_capsule_ledger_deny_truncate',
    ],
)
def test_staged_db_guard_rejects_disabled_or_missing_immutability_triggers(missing):
    triggers = [item for item in _postgres_triggers() if item[0] != missing]
    with pytest.raises(ValueError, match='missing or disabled'):
        _require_postgres_ledger_write_once_guards(
            _PostgresReviewSession(triggers, _postgres_state()),
        )
    disabled = [(name, 'D' if name == missing else mode) for name, mode in _postgres_triggers()]
    with pytest.raises(ValueError, match='missing or disabled'):
        _require_postgres_ledger_write_once_guards(
            _PostgresReviewSession(disabled, _postgres_state()),
        )


@pytest.mark.parametrize(
    'field,bad_value',
    [
        ('fsync_setting', 'off'),
        ('sync_commit', 'off'),
        ('replication_role', 'replica'),
        ('elevated', True),
        ('is_owner', True),
        ('member_of_owner', True),
        ('may_insert', False),
        ('may_update', True),
        ('may_delete', True),
        ('may_truncate', True),
    ],
)
def test_staged_db_guard_rejects_privileged_or_nondurable_execution_role(field, bad_value):
    state = _postgres_state()
    state[field] = bad_value
    with pytest.raises(ValueError, match='role, trigger or WAL'):
        _require_postgres_ledger_write_once_guards(
            _PostgresReviewSession(_postgres_triggers(), state),
        )

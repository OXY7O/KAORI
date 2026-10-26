"""Scope admission rejects unqualified per-source Vault Secret inventory."""

from datetime import UTC, datetime, timedelta

import pytest

from app.secrets_pki.registry_scope import admit_secret_registry_scope

AT = datetime(2026, 10, 22, 12, tzinfo=UTC)


def accepted(**changes):
    args = {
        'has_view_permission': True,
        'scope_policy_enforced': True,
        'approved_instance_ids': frozenset({7}),
        'requested_instance_id': 7,
        'observed_record_instance_ids': (7, 7),
        'source_ready': True,
        'generation_complete': True,
        'committed_at': AT,
        'now': AT + timedelta(minutes=2),
    }
    args.update(changes)
    return admit_secret_registry_scope(**args)


def test_explicit_qualified_source_returns_only_count_and_no_detail_permission():
    value = accepted()
    assert value.status == 'qualified'
    assert value.eligible_record_count == 2
    assert not value.permitted_for_detail
    assert 'vault' not in repr(value)
    assert not hasattr(value, 'path')
    assert accepted(observed_record_instance_ids=()).eligible_record_count == 0


@pytest.mark.parametrize(
    'change',
    [
        {'has_view_permission': False},
        {'scope_policy_enforced': False},
        {'approved_instance_ids': None},
        {'approved_instance_ids': frozenset()},
        {'approved_instance_ids': frozenset({8})},
        {'requested_instance_id': 8},
        {'approved_instance_ids': frozenset({0, 7})},
        {'requested_instance_id': True},
    ],
)
def test_missing_or_wrong_scope_never_exposes_inventory_count(change):
    value = accepted(**change)
    assert value.status == 'scope_denied'
    assert value.eligible_record_count is None


@pytest.mark.parametrize(
    'change',
    [
        {'source_ready': False},
        {'generation_complete': False},
        {'committed_at': None},
        {'committed_at': AT - timedelta(hours=26)},
        {'committed_at': AT + timedelta(hours=1)},
        {'committed_at': AT.replace(tzinfo=None)},
        {'observed_record_instance_ids': (7, 8)},
        {'observed_record_instance_ids': (7,) * 201},
        {'observed_record_instance_ids': (True,)},
        {'observed_record_instance_ids': ('private/path',)},
    ],
)
def test_stale_incomplete_mixed_or_broken_evidence_is_unknown(change):
    value = accepted(**change)
    assert value.status == 'source_unknown'
    assert value.eligible_record_count is None

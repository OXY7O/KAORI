"""Pilot access correlation is exact, bounded, redacted and non-authorizing."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.infrastructure_automation.kubernetes import committed_host_access as subject

NOW = datetime(2026, 11, 24, 6, tzinfo=UTC)


def _members():
    connection = SimpleNamespace(id=17)
    assignments = [
        SimpleNamespace(id=index, integration_instance_id=17, enabled=True, host_id=f'asset-{index}')
        for index in range(1, 4)
    ]
    return connection, assignments


def _reference(connection, assignment, now):
    return (assignment.host_id, 'a' * 64, 'b' * 64, NOW.isoformat())


def test_three_exact_members_are_order_independent(monkeypatch):
    connection, members = _members()
    monkeypatch.setattr(subject, '_member_reference', _reference)
    digest = subject.committed_pilot_access_fingerprint(connection, members, now=NOW)
    assert digest and len(digest) == 64
    assert digest == subject.committed_pilot_access_fingerprint(connection, list(reversed(members)), now=NOW)
    assert 'asset-' not in digest


@pytest.mark.parametrize('field', ['host_revision', 'reference', 'generation'])
def test_each_reference_generation_change_invalidates_aggregate(monkeypatch, field):
    connection, members = _members()
    monkeypatch.setattr(subject, '_member_reference', _reference)
    digest = subject.committed_pilot_access_fingerprint(connection, members, now=NOW)

    def changed(connection, assignment, now):
        value = list(_reference(connection, assignment, now))
        if assignment.id == 2:
            value[{'host_revision': 1, 'reference': 2, 'generation': 3}[field]] = 'changed'
        return tuple(value)

    monkeypatch.setattr(subject, '_member_reference', changed)
    assert digest != subject.committed_pilot_access_fingerprint(connection, members, now=NOW)


def test_missing_duplicate_disabled_and_cross_scope_members_fail_closed(monkeypatch):
    connection, members = _members()
    monkeypatch.setattr(subject, '_member_reference', _reference)
    assert subject.committed_pilot_access_fingerprint(connection, members[:2], now=NOW) is None
    assert subject.committed_pilot_access_fingerprint(connection, [members[0]] * 3, now=NOW) is None
    members[0].enabled = False
    assert subject.committed_pilot_access_fingerprint(connection, members, now=NOW) is None
    members[0].enabled = True
    members[0].integration_instance_id = 99
    assert subject.committed_pilot_access_fingerprint(connection, members, now=NOW) is None
    members[0].integration_instance_id = 17
    monkeypatch.setattr(subject, '_member_reference', lambda *args: None)
    assert subject.committed_pilot_access_fingerprint(connection, members, now=NOW) is None

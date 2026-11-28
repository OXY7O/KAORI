"""Bounded server-side session lifecycle policy and SQL generation guards (#5282)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.access.authentication import session_lifecycle as lifecycle
from app.models import User

NOW = datetime(2026, 11, 28, 0, 0, tzinfo=UTC)


def actor(*, privileged: bool = False, issued_minutes: int = 0, idle_minutes: int = 0) -> User:
    return User(
        id=42,
        is_super_admin=privileged,
        auth_session_version=8,
        auth_session_issued_at=NOW - timedelta(minutes=issued_minutes),
        auth_session_activity_at=NOW - timedelta(minutes=idle_minutes),
    )


@pytest.mark.parametrize(
    ('privileged', 'idle_minutes', 'issued_minutes', 'reason'),
    (
        (True, 15, 15, 'idle_timeout'),
        (False, 30, 30, 'idle_timeout'),
        (True, 0, 240, 'absolute_timeout'),
        (False, 0, 480, 'absolute_timeout'),
    ),
)
def test_deadlines_deny_at_exact_boundary(privileged, idle_minutes, issued_minutes, reason) -> None:
    assert lifecycle.session_deadlines(
        actor(privileged=privileged, issued_minutes=issued_minutes, idle_minutes=idle_minutes),
        lifecycle.SessionPolicy(),
        NOW,
    ) == reason


def test_active_session_payload_and_no_absolute_reset() -> None:
    user = actor(privileged=True, issued_minutes=239, idle_minutes=14)
    policy = lifecycle.SessionPolicy()
    deadlines = lifecycle.session_deadlines(user, policy, NOW)
    assert isinstance(deadlines, lifecycle.SessionDeadlines)
    assert deadlines.payload(NOW, policy) == {
        'idle_remaining_seconds': 60,
        'absolute_remaining_seconds': 60,
        'warning_seconds': 120,
    }
    user.auth_session_activity_at = NOW
    extended = lifecycle.session_deadlines(user, policy, NOW)
    assert isinstance(extended, lifecycle.SessionDeadlines)
    assert extended.absolute == deadlines.absolute
    assert extended.idle > deadlines.idle


def test_unqualified_and_malformed_session_state_is_denied() -> None:
    user = actor()
    user.auth_session_issued_at = None
    assert lifecycle.session_deadlines(user, lifecycle.SessionPolicy(), NOW) == 'session_state_invalid'
    user.auth_session_issued_at = NOW
    user.auth_session_activity_at = NOW - timedelta(seconds=1)
    assert lifecycle.session_deadlines(user, lifecycle.SessionPolicy(), NOW) == 'session_state_invalid'


@pytest.mark.parametrize(
    'overrides',
    (
        {'privileged_idle_minutes': 4},
        {'privileged_idle_minutes': 40},
        {'regular_absolute_hours': 25},
        {'privileged_absolute_hours': 9},
        {'warning_minutes': 0},
        {'privileged_idle_minutes': 5, 'warning_minutes': 5},
    ),
)
def test_invalid_policy_fails_closed(overrides) -> None:
    with pytest.raises(ValueError):
        lifecycle.SessionPolicy(**overrides)


class Store:
    def __init__(self, matched: bool) -> None:
        self.matched = matched
        self.statements = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, statement):
        self.statements.append(str(statement).lower())
        return SimpleNamespace(scalar_one_or_none=lambda: 42 if self.matched else None)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_activity_update_guards_generation_and_both_deadlines(monkeypatch) -> None:
    store = Store(matched=True)
    monkeypatch.setattr(lifecycle, 'db', SimpleNamespace(session=store))
    assert lifecycle.refresh_activity(actor(), 8, lifecycle.SessionPolicy(), NOW)
    statement = store.statements[0]
    assert 'users.auth_session_version =' in statement
    assert 'users.auth_session_issued_at >' in statement
    assert 'users.auth_session_activity_at >' in statement
    assert 'case when' in statement
    assert store.commits == 1

    store.matched = False
    assert not lifecycle.refresh_activity(actor(), 8, lifecycle.SessionPolicy(), NOW)
    assert store.commits == 1 and store.rollbacks == 1


def test_expiry_compare_and_swap_does_not_revoke_newer_activity(monkeypatch) -> None:
    store = Store(matched=False)
    monkeypatch.setattr(lifecycle, 'db', SimpleNamespace(session=store))
    assert not lifecycle.expire_generation(actor(idle_minutes=0), 8, 'idle_timeout')
    statement = store.statements[0]
    assert 'users.auth_session_version =' in statement
    assert 'users.auth_session_issued_at =' in statement
    assert 'users.auth_session_activity_at =' in statement
    assert store.commits == 0 and store.rollbacks == 1


def test_logout_revocation_only_stages_exact_generation(monkeypatch) -> None:
    store = Store(matched=True)
    monkeypatch.setattr(lifecycle, 'db', SimpleNamespace(session=store))
    assert lifecycle.revoke_generation(42, 8)
    assert 'users.auth_session_version =' in store.statements[0]
    assert store.commits == 0

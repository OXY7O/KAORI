"""AL-01 boundary and DML contracts; SQLite is not PostgreSQL concurrency evidence."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.access.authentication import lockout_state
from app.access.authentication.lockout_policy import (
    LockoutGate,
    LockoutMode,
    LockoutState,
    apply_outcome,
    inspect_state,
)
from app.models.authentication_security import AuthenticationAccountLockout
from app.models.notification import Notification

NOW = datetime(2026, 11, 28, tzinfo=UTC)


@pytest.mark.parametrize('mode', (LockoutMode.MONITOR_ONLY, LockoutMode.ENFORCED))
def test_thresholds_cooldown_lock_and_exact_expiry(mode: LockoutMode) -> None:
    now = NOW
    state = LockoutState()
    for count in range(1, 11):
        decision = inspect_state(mode, state, now=now)
        assert decision.gate == LockoutGate.OPEN
        state = apply_outcome(decision, password_valid=False, now=now)
        assert len(state.failures) == count
        if 3 <= count <= 9:
            deadline = now + timedelta(seconds=5 if count < 5 else 30)
            assert state.cooldown_until == deadline
            gate = inspect_state(mode, state, now=deadline - timedelta(microseconds=1))
            assert gate.gate == LockoutGate.COOLDOWN
            assert gate.blocked == (mode == LockoutMode.ENFORCED)
            assert apply_outcome(gate, password_valid=None, now=now) == state
            now = deadline
        else:
            assert state.cooldown_until is None
            now += timedelta(seconds=1)
    assert state.locked_until == state.failures[-1] + timedelta(minutes=15)
    assert state.locked_until is not None
    gate = inspect_state(mode, state, now=state.locked_until - timedelta(microseconds=1))
    assert gate.gate == LockoutGate.LOCKED
    assert apply_outcome(gate, password_valid=None, now=now) == state
    if mode == LockoutMode.ENFORCED:
        with pytest.raises(ValueError):
            apply_outcome(gate, password_valid=True, now=now)
    else:
        assert apply_outcome(gate, password_valid=False, now=now) == state
        assert apply_outcome(gate, password_valid=True, now=now) == LockoutState()
    expired = inspect_state(mode, state, now=state.locked_until)
    assert expired.auto_unlocked and not expired.blocked
    assert expired.state == LockoutState()
    assert len(apply_outcome(expired, password_valid=False, now=state.locked_until).failures) == 1


def test_true_rolling_boundary_success_and_disabled() -> None:
    state = LockoutState((NOW - timedelta(minutes=15), NOW - timedelta(minutes=14)))
    decision = inspect_state(LockoutMode.ENFORCED, state, now=NOW)
    assert decision.state.failures == (NOW - timedelta(minutes=14),)
    assert len(apply_outcome(decision, password_valid=False, now=NOW).failures) == 2
    assert apply_outcome(decision, password_valid=True, now=NOW) == LockoutState()
    disabled = inspect_state(LockoutMode.DISABLED, state, now=NOW)
    assert not disabled.blocked
    assert apply_outcome(disabled, password_valid=False, now=NOW) == LockoutState()


def test_corrupt_state_fails_closed() -> None:
    with pytest.raises(ValueError):
        inspect_state(LockoutMode.ENFORCED, LockoutState((NOW + timedelta(seconds=1),)), now=NOW)
    with pytest.raises(ValueError):
        inspect_state(LockoutMode.ENFORCED, LockoutState(locked_until=NOW), now=NOW)


@pytest.mark.parametrize('failure', ('none', 'audit_stage', 'audit_insert'))
def test_state_and_audit_share_transaction(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(sa.text(
            'CREATE TABLE users (id INTEGER PRIMARY KEY, auth_source TEXT, is_active BOOLEAN, '
            'deleted_at DATETIME, is_super_admin BOOLEAN, password_hash TEXT)'
        ))
        connection.execute(sa.text(
            'CREATE TABLE authentication_security_policies '
            '(id INTEGER PRIMARY KEY, lockout_mode TEXT, lockout_revision BIGINT)'
        ))
        connection.execute(sa.text(
            "INSERT INTO users VALUES (1, 'database', true, NULL, false, 'test'), "
            "(2, 'ldap_directory', true, NULL, false, ''), (3, 'database', true, NULL, true, 'test'), "
            "(4, 'database', false, NULL, false, 'test')"
        ))
        connection.execute(sa.text(
            "INSERT INTO authentication_security_policies VALUES (1, 'disabled', 1)"
        ))
        AuthenticationAccountLockout.__table__.create(connection)
        Notification.__table__.create(connection)
    with Session(engine) as store:
        monkeypatch.setattr(lockout_state, 'db', SimpleNamespace(session=store))
        monkeypatch.setattr(lockout_state, '_clock', lambda: NOW)
        for user_id in (2, 3, 4, 999):
            assert lockout_state.lock_account_state(user_id) is None
        disabled = lockout_state.lock_account_state(1)
        assert disabled is not None
        lockout_state.stage_password_outcome(disabled, password_valid=False)
        store.commit()
        assert store.get(AuthenticationAccountLockout, 1) is None
        store.execute(sa.text(
            "UPDATE authentication_security_policies SET lockout_mode='monitor_only', lockout_revision=2"
        ))
        store.commit()
        context = lockout_state.lock_account_state(1)
        assert context is not None
        if failure == 'audit_stage':
            # Audit construction failure after the state was staged is not swallowed.
            with monkeypatch.context() as patch:
                patch.setattr(lockout_state, '_event', Mock(side_effect=RuntimeError('audit failure')))
                with pytest.raises(RuntimeError):
                    lockout_state.stage_password_outcome(context, password_valid=False)
            store.rollback()
            assert store.get(AuthenticationAccountLockout, 1) is None
            assert store.execute(sa.select(sa.func.count()).select_from(Notification)).scalar_one() == 0
        elif failure == 'audit_insert':
            store.execute(sa.text(
                "CREATE TRIGGER reject_lockout_audit BEFORE INSERT ON notifications "
                "BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END"
            ))
            lockout_state.stage_password_outcome(context, password_valid=False)
            # Flush the pending account state independently to demonstrate
            # that a later audit DML failure rolls back even executed writes.
            pending = next(item for item in store.new if isinstance(item, AuthenticationAccountLockout))
            store.flush([pending])
            with pytest.raises(sa.exc.IntegrityError):
                store.commit()
            store.rollback()
            assert store.get(AuthenticationAccountLockout, 1) is None
            assert store.execute(sa.select(sa.func.count()).select_from(Notification)).scalar_one() == 0
        else:
            lockout_state.stage_password_outcome(context, password_valid=False)
            store.commit()
            record = store.get(AuthenticationAccountLockout, 1)
            assert record is not None and record.failure_times == [NOW.isoformat()]
            audit = store.execute(sa.select(Notification)).scalar_one()
            assert audit.user_id == 1 and audit.deck_visible is False
            assert audit.metadata_json is not None and audit.metadata_json['password_outcome'] == 'invalid'
            store.execute(sa.text(
                "UPDATE authentication_security_policies SET lockout_mode='enforced', lockout_revision=3"
            ))
            store.commit()
            activated = lockout_state.lock_account_state(1)
            assert activated is not None and activated.decision.state == LockoutState()
            lockout_state.stage_password_outcome(activated, password_valid=False)
            store.commit()
            record = store.get(AuthenticationAccountLockout, 1)
            assert record is not None and record.policy_revision == 3 and len(record.failure_times) == 1
    engine.dispose()

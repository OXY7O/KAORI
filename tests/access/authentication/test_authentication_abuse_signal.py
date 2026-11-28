"""AL-05 observe-only committed evidence, bounds and freshness contracts."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.intelligence.alert_signals import authentication as signal


def _login(reason: str = 'invalid_credentials', ip: str = '192.0.2.1') -> dict[str, str]:
    return {
        'audit_schema': 'authentication.v2', 'access_action': 'login',
        'result': 'failed', 'reason_code': reason, 'auth_source': 'database',
        'ip_address': ip, 'username': 'fixture-private-identity',
    }


def _security(action: str, mode: str = 'enforced') -> dict[str, str]:
    return {'audit_schema': 'authentication.security.v1', 'access_action': action, 'policy_mode': mode}


def test_closed_window_is_settled_and_nonoverlapping() -> None:
    start, end = signal.closed_window(datetime(2026, 11, 28, 12, 16, 59, tzinfo=UTC))
    assert (start.hour, start.minute, end.hour, end.minute) == (11, 45, 12, 0)
    assert signal.closed_window(datetime(2026, 11, 28, 12, 17, tzinfo=UTC))[0] == end


def test_indicators_separate_rejections_and_control_evidence() -> None:
    rows = [(_login(ip=f'192.0.2.{i % 5 + 1}'), i % 5 + 1, i % 5 == 0) for i in range(30)]
    rows.extend([
        (_login('bot_challenge_failed'), None, None),
        (_login('rate_limited'), None, None),
        (_login('provider_unavailable'), 1, True),
        (_security('lockout_threshold_reached'), 1, False),
        (_security('lockout_threshold_reached', 'monitor_only'), 1, False),
        (_security('mfa_challenge_rejected'), 1, True),
        *[(_security('identity_budget_exceeded'), None, None)] * 10,
    ])
    data = signal.summarize_abuse(rows)
    assert data['credential_rejections'] == 30
    assert data['known_targets'] == data['distinct_observed_sources'] == 5
    assert data['peak_current_recovery_principal_rejections'] == 6
    assert data['endpoint_rate_limited'] == data['challenge_rejections'] == 1
    assert data['enforced_lock_transitions'] == data['monitor_threshold_observations'] == 1
    assert data['identity_budget_observations'] == 10
    assert set(data['indicators']) == {
        'elevated_credential_rejections', 'multi_target_rejection_pattern',
        'multi_source_rejection_pattern', 'recovery_principal_rejection_pattern',
        'shared_budget_pressure', 'enforced_lock_transition',
    }
    assert 'fixture-private-identity' not in str(data) and '192.0.2.' not in str(data)


def test_unknown_targets_and_sample_cap() -> None:
    data = signal.summarize_abuse([(_login(ip='invalid'), None, None)] * (signal.MAX_ROWS + 1))
    assert data['sample_rows'] == signal.MAX_ROWS and data['coverage'] == 'partial'
    assert data['known_targets'] == data['distinct_observed_sources'] == 0
    assert 'sample_capacity_exceeded' in data['indicators']
    assert 'multi_target_rejection_pattern' not in data['indicators']


@pytest.mark.parametrize('case', ('disabled', 'same_window', 'commit_failure', 'success'))
def test_atomic_worker_boundary(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    app = Flask(__name__)
    app.config['AUTH_ABUSE_SIGNAL_ENABLED'] = case != 'disabled'
    now = datetime(2026, 11, 28, 12, 20, tzinfo=UTC)
    _, end = signal.closed_window(now)
    store = Mock()
    store.get_bind.return_value.dialect.name = 'postgresql'
    store.execute.return_value.scalar_one.return_value = now
    store.execute.return_value.tuples.return_value.all.return_value = [(_login(), 1, True)] * 5
    store.execute.return_value.scalars.return_value.all.return_value = list(range(1, 12))
    snap = SimpleNamespace(generated_at=end if case == 'same_window' else None)
    lock = Mock(return_value=snap)
    notify = Mock()
    monkeypatch.setattr(signal, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(signal, '_snapshot_locked', lock)
    monkeypatch.setattr(signal, '_stage_notifications', notify)
    if case == 'commit_failure':
        store.commit.side_effect = SQLAlchemyError('fixture commit failure')
    with app.app_context():
        if case == 'commit_failure':
            with pytest.raises(SQLAlchemyError):
                signal.refresh_authentication_abuse_signal()
            store.rollback.assert_called_once()
        else:
            result = signal.refresh_authentication_abuse_signal()
            assert result['state'] == {'disabled': 'disabled', 'same_window': 'already_evaluated',
                                       'success': 'observed'}[case]
    if case in ('disabled', 'same_window'):
        notify.assert_not_called()
        store.commit.assert_not_called()
    else:
        payload, recipients = notify.call_args.args
        assert len(recipients) == signal.MAX_RECIPIENTS and payload['recipient_limit_reached']
        assert snap.payload_json == payload
        store.commit.assert_called_once()
    if case == 'disabled':
        lock.assert_not_called()
        store.execute.assert_not_called()


@pytest.mark.parametrize('state', ('missing', 'unavailable', 'stale', 'partial', 'fresh'))
def test_read_posture(monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    app = Flask(__name__)
    app.config['AUTH_ABUSE_SIGNAL_ENABLED'] = True
    store = Mock()
    snap = SimpleNamespace(
        status='failed' if state == 'unavailable' else 'ready',
        payload_json={'schema_version': 1, 'coverage': 'partial' if state == 'partial' else 'bounded_window'},
        expires_at=datetime.now(UTC) + timedelta(minutes=-1 if state == 'stale' else 5),
    )
    store.execute.return_value.scalar_one_or_none.return_value = None if state == 'missing' else snap
    monkeypatch.setattr(signal, 'db', SimpleNamespace(session=store))
    with app.app_context():
        result = signal.read_authentication_abuse_signal()
    assert result['state'] == state
    assert (result['payload'] is not None) == (state in ('fresh', 'partial'))

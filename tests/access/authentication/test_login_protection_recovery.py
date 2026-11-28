"""AL-04 independent rollback, revision fencing and unchanged control boundaries."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication import break_glass
from app.access.authentication.mfa import service as mfa
from app.commands import authentication as commands
from app.models.authentication_security import AuthenticationMfaFactor
from app.models.notification import Notification
from app.models.user import User


def _recover(*, revision: int = 7, acknowledged: bool = True):
    return break_glass.recover_login_protection(
        username='fixture-admin',
        operator='operator-42',
        ticket='INC-123',
        reason='Confirmed identity budget availability incident',
        password='fixture-password',
        code='123456',
        acknowledged=acknowledged,
        expected_revision=revision,
    )


@pytest.mark.parametrize(
    'case',
    ('enforced', 'monitor_only', 'disabled', 'stale', 'missing_policy', 'unauthorized',
     'web', 'no_ack', 'unknown', 'external', 'regular', 'inactive', 'bad_password', 'replay', 'audit', 'commit'),
)
def test_rollback_revision_proof_and_audit(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    actor = User(
        id=42, username='fixture-admin', email='admin@example.invalid',
        auth_source='ldap' if case == 'external' else 'database',
        is_super_admin=case != 'regular', account_is_active=case != 'inactive',
        auth_session_version=9, password_hash='fixture',
    )
    factor = AuthenticationMfaFactor(
        user_id=42, enabled=True, totp_secret='fixture-seed',
        recovery_hashes=['fixture-hash'], last_accepted_step=1,
    )
    store = Mock()
    store.execute.return_value.scalar_one_or_none.return_value = None if case == 'unknown' else actor
    mode = case if case in ('enforced', 'monitor_only', 'disabled') else 'enforced'
    store.execute.return_value.one_or_none.return_value = None if case == 'missing_policy' else (mode, 7)
    if case == 'commit':
        store.commit.side_effect = SQLAlchemyError('fixture commit failure')
    monkeypatch.setattr(break_glass, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(mfa, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(User, 'check_password', lambda self, _password: case != 'bad_password')
    monkeypatch.setattr(mfa, '_locked_factor', Mock(return_value=factor))
    monkeypatch.setattr(mfa, '_accepted_step', Mock(return_value=None if case == 'replay' else 2))
    if case == 'audit':
        monkeypatch.setattr(break_glass, '_stage_event', Mock(side_effect=SQLAlchemyError('fixture audit failure')))
    app = Flask(__name__)
    app.config.update(
        AUTH_BREAK_GLASS_RECOVERY_ALLOWED=case != 'unauthorized',
        RATELIMIT_ENABLED=True, RATELIMIT_STORAGE_URI='redis://unreachable.invalid:6379/2',
        AUTH_LOGIN_RATE_LIMIT='5 per minute',
    )
    before = dict(app.config)
    with app.app_context():
        if case == 'web':
            with app.test_request_context('/fixture'):
                with pytest.raises(break_glass.BreakGlassDenied):
                    _recover()
        elif case in ('enforced', 'monitor_only', 'disabled'):
            result = _recover()
            changed = case != 'disabled'
            assert result.previous_mode == mode and result.new_mode == 'disabled'
            assert result.previous_revision == 7 and result.new_revision == 7 + int(changed)
            assert store.execute.call_count == 2 + int(changed)
            if changed:
                values = store.execute.call_args_list[-1].args[0].compile().params
                assert values['lockout_mode'] == 'disabled' and values['lockout_revision'] == 8
                assert set(values) == {'lockout_mode', 'lockout_revision', 'updated_at', 'id_1'}
            assert factor.last_accepted_step == 2
            assert factor.recovery_hashes == ['fixture-hash'] and actor.auth_session_version == 9
            proof, recovery = (call.args[0] for call in store.add.call_args_list)
            assert isinstance(proof, Notification) and isinstance(recovery, Notification)
            assert recovery.metadata_json is not None
            assert recovery.metadata_json['access_action'] == 'lockout_break_glass_recovery'
            assert recovery.metadata_json['previous_revision'] == 7
            assert recovery.metadata_json['new_revision'] == result.new_revision
            assert recovery.metadata_json['correlation_id'] == result.correlation
            assert recovery.metadata_json['result'] == ('changed' if changed else 'unchanged')
            assert recovery.deck_visible and recovery.actor_key == 'user:42'
            for secret in ('fixture-password', '123456', 'fixture-seed', 'fixture-hash'):
                assert secret not in str(recovery.metadata_json)
            store.commit.assert_called_once()
            store.rollback.assert_not_called()
        else:
            with pytest.raises((ValueError, SQLAlchemyError)):
                _recover(revision=6 if case == 'stale' else 7, acknowledged=case != 'no_ack')
    assert dict(app.config) == before
    if case not in ('enforced', 'monitor_only', 'disabled'):
        store.rollback.assert_called_once()
        if case != 'commit':
            store.commit.assert_not_called()
        if case in ('unauthorized', 'web', 'no_ack'):
            store.execute.assert_not_called()
        if case not in ('audit', 'commit'):
            assert factor.last_accepted_step == 1


def test_rollback_cli_denies_noninteractive_before_read(monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    app.cli.add_command(commands.recover_login_protection_command)
    read = Mock()
    monkeypatch.setattr(commands, 'read_login_policy', read)
    runner = app.test_cli_runner()
    result = runner.invoke(args=['recover-login-protection'])
    assert result.exit_code != 0 and 'not authorized' in result.output
    app.config['AUTH_BREAK_GLASS_RECOVERY_ALLOWED'] = True
    result = runner.invoke(args=['recover-login-protection'])
    assert result.exit_code != 0 and 'interactive management terminal' in result.output
    read.assert_not_called()


def test_command_and_activation_boundaries() -> None:
    root = Path(__file__).resolve().parents[3]
    cli = (root / 'app/commands/authentication.py').read_text()
    registration = (root / 'app/commands/__init__.py').read_text()
    routes = (root / 'app/access/authentication/routes.py').read_text()
    governance = (root / 'app/access/authentication/lockout_governance.py').read_text()
    service = (root / 'app/access/authentication/break_glass.py').read_text()
    assert "@click.command('recover-login-protection')" in cli
    assert 'app.cli.add_command(recover_login_protection_command)' in registration
    assert 'recover_login_protection' not in routes
    rollback = service.split('def recover_login_protection(', 1)[1]
    assert 'probe_shared_login_protection' not in rollback
    assert 'lockout_mode=LockoutMode.DISABLED.value' in rollback
    assert 'previous != LockoutMode.MONITOR_ONLY' in governance
    assert 'probe_shared_login_protection()' in governance
    for template in ('.env.example', 'deploy/env/app.env.example'):
        assert 'AUTH_BREAK_GLASS_RECOVERY_ALLOWED=false' in (root / template).read_text()

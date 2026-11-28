"""BP-03 isolated management recovery transaction and command contracts."""

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


def _recover(*, acknowledged: bool = True):
    return break_glass.recover_bot_protection(
        username='fixture-admin', operator='operator-42', ticket='INC-123',
        reason='Confirmed provider service outage', password='fixture-password',
        code='123456', acknowledged=acknowledged,
    )


def _app(*, enabled: bool = True) -> Flask:
    app = Flask(__name__)
    app.config['AUTH_BREAK_GLASS_RECOVERY_ALLOWED'] = enabled
    return app


@pytest.mark.parametrize('case', (
    'changed', 'unchanged', 'disabled', 'web', 'no_ack', 'unknown', 'external',
    'regular', 'inactive', 'bad_password', 'replay', 'audit', 'commit',
))
def test_recovery_transaction_and_assurance(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    actor = User(
        id=42, username='fixture-admin', email='admin@example.invalid', auth_source='database',
        is_super_admin=case != 'regular', account_is_active=case != 'inactive',
        auth_session_version=7, password_hash='fixture',
    )
    if case == 'external':
        actor.auth_source = 'ldap'
    factor = AuthenticationMfaFactor(
        user_id=42, enabled=True, totp_secret='fixture-seed', recovery_hashes=['fixture-hash'],
        last_accepted_step=1,
    )
    store = Mock()
    store.execute.return_value.scalar_one_or_none.side_effect = [
        None if case == 'unknown' else actor, 'disabled' if case == 'unchanged' else 'always',
    ]
    if case == 'commit':
        store.commit.side_effect = SQLAlchemyError('fixture commit failure')
    monkeypatch.setattr(break_glass, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(mfa, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(User, 'check_password', lambda self, _password: case != 'bad_password')
    monkeypatch.setattr(mfa, '_locked_factor', Mock(return_value=factor))
    monkeypatch.setattr(mfa, '_accepted_step', Mock(return_value=None if case == 'replay' else 2))
    if case == 'audit':
        monkeypatch.setattr(break_glass, '_stage_event', Mock(side_effect=SQLAlchemyError('fixture audit failure')))
    app = _app(enabled=case != 'disabled')
    with app.app_context():
        if case == 'web':
            with app.test_request_context('/fixture'):
                with pytest.raises(break_glass.BreakGlassDenied):
                    _recover()
        elif case in ('changed', 'unchanged'):
            result = _recover()
            assert result.previous_mode == ('always' if case == 'changed' else 'disabled')
            assert result.new_mode == 'disabled'
            assert len(result.correlation) == 32
            assert store.execute.call_count == (3 if case == 'changed' else 2)
            if case == 'changed':
                mutation = store.execute.call_args_list[-1].args[0]
                values = mutation.compile().params
                assert values['bot_mode'] == 'disabled' and values['bot_tested_at'] is None
                assert set(values) == {'bot_mode', 'bot_tested_at', 'updated_at', 'id_1'}
            assert factor.last_accepted_step == 2
            assert factor.recovery_hashes == ['fixture-hash'] and actor.auth_session_version == 7
            proof, recovery = (call.args[0] for call in store.add.call_args_list)
            assert isinstance(proof, Notification) and isinstance(recovery, Notification)
            assert proof.metadata_json is not None
            assert proof.metadata_json['trigger_type'] == 'cli'
            assert proof.metadata_json['session_reference'] is None
            assert recovery.actor_key == 'user:42' and recovery.deck_visible
            assert recovery.metadata_json is not None
            assert recovery.metadata_json['operator_reference_verified'] is False
            assert recovery.metadata_json['correlation_id'] == result.correlation
            assert recovery.metadata_json['result'] == case
            for secret in ('fixture-password', '123456', 'fixture-seed', 'fixture-hash'):
                assert secret not in str(recovery.metadata_json)
            store.commit.assert_called_once()
            store.rollback.assert_not_called()
        else:
            with pytest.raises((ValueError, SQLAlchemyError)):
                _recover(acknowledged=case != 'no_ack')
    if case not in ('changed', 'unchanged'):
        store.rollback.assert_called_once()
        if case != 'commit':
            store.commit.assert_not_called()
        if case in ('disabled', 'web', 'no_ack'):
            store.execute.assert_not_called()
        if case in ('unknown', 'external', 'regular', 'inactive', 'bad_password', 'replay'):
            assert factor.last_accepted_step == 1


def test_command_refuses_disabled_or_noninteractive(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(enabled=False)
    app.cli.add_command(commands.recover_bot_protection_command)
    recover = Mock()
    monkeypatch.setattr(commands, 'recover_bot_protection', recover)
    runner = app.test_cli_runner()
    result = runner.invoke(args=['recover-bot-protection'])
    assert result.exit_code != 0 and 'not authorized' in result.output
    app.config['AUTH_BREAK_GLASS_RECOVERY_ALLOWED'] = True
    result = runner.invoke(args=['recover-bot-protection'])
    assert result.exit_code != 0 and 'interactive management terminal' in result.output
    recover.assert_not_called()


def test_recovery_is_cli_only_and_restoration_uses_existing_guard() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / 'app/commands/authentication.py').read_text()
    routes = (root / 'app/access/authentication/routes.py').read_text()
    policy = (root / 'app/access/authentication_security/__init__.py').read_text()
    assert "@click.command('recover-bot-protection')" in source
    assert 'hide_input=True' in source
    assert 'recover_bot_protection' not in routes and 'recover_bot_protection' not in policy
    assert 'if not ready or config_changed or not recent:' in policy
    assert 'verify_turnstile(' in policy

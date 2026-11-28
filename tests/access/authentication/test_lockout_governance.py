"""Governed lockout policy and exact-target recovery contracts (#5326)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from app.access.authentication import lockout_governance as governance
from app.access.authentication.lockout_policy import LockoutMode, LockoutState, inspect_state
from app.access.authentication.lockout_state import LockedAccountState
from app.models.authentication_security import AuthenticationAccountLockout
from app.models.user import User

EVIDENCE = governance.GovernanceEvidence('INC-123', 'Verified incident recovery request')


def test_evidence_is_bounded_and_rejects_sensitive_assignment() -> None:
    assert governance.GovernanceEvidence.parse(' INC-123 ', 'Verified incident recovery request') == EVIDENCE
    for ticket, reason in (
        ('', 'Verified incident recovery request'),
        ('INC-123', 'short'),
        ('INC-123', 'password=fixture-sensitive'),
        ('INC-123', 'x' * 301),
    ):
        with pytest.raises(governance.LockoutGovernanceDenied):
            governance.GovernanceEvidence.parse(ticket, reason)


def test_activation_defaults_hold_and_enforcement_requires_monitor(monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    probe = Mock()
    store = Mock()
    store.execute.return_value.scalar_one_or_none.return_value = 42
    monkeypatch.setattr(governance, 'probe_shared_login_protection', probe)
    monkeypatch.setattr(governance, 'db', SimpleNamespace(session=store))
    with app.app_context():
        with pytest.raises(governance.LockoutGovernanceDenied):
            governance.validate_activation(LockoutMode.DISABLED, LockoutMode.MONITOR_ONLY)
        probe.assert_not_called()
        app.config['AUTH_LOCKOUT_MONITOR_ALLOWED'] = True
        governance.validate_activation(LockoutMode.DISABLED, LockoutMode.MONITOR_ONLY)
        with pytest.raises(governance.LockoutGovernanceDenied):
            governance.validate_activation(LockoutMode.MONITOR_ONLY, LockoutMode.ENFORCED)
        app.config['AUTH_LOCKOUT_ENFORCEMENT_ALLOWED'] = True
        with pytest.raises(governance.LockoutGovernanceDenied):
            governance.validate_activation(LockoutMode.DISABLED, LockoutMode.ENFORCED)
        governance.validate_activation(LockoutMode.MONITOR_ONLY, LockoutMode.ENFORCED)
        assert probe.call_count == 2
        governance.validate_activation(LockoutMode.ENFORCED, LockoutMode.DISABLED)
        assert probe.call_count == 2
        store.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(governance.LockoutGovernanceDenied):
            governance.validate_activation(LockoutMode.DISABLED, LockoutMode.MONITOR_ONLY)


@pytest.mark.parametrize('requested,expected_revision,changed', (
    (LockoutMode.DISABLED, 2, False),
    (LockoutMode.MONITOR_ONLY, 2, True),
    (LockoutMode.MONITOR_ONLY, 1, None),
))
def test_policy_revision_and_step_up_are_staged(
    monkeypatch: pytest.MonkeyPatch, requested: LockoutMode, expected_revision: int, changed: bool | None
) -> None:
    actor = User(id=42, auth_source='database', is_super_admin=True)
    store = Mock()
    store.execute.return_value.one_or_none.return_value = ('disabled', 2)
    monkeypatch.setattr(governance, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(governance, '_lock_users', Mock(return_value={42: actor}))
    monkeypatch.setattr(governance, '_validate_actor', Mock(return_value=actor))
    monkeypatch.setattr(governance, 'validate_activation', Mock())
    proof = Mock()
    event = Mock(return_value=object())
    monkeypatch.setattr(governance, '_step_up', proof)
    monkeypatch.setattr(governance, '_event', event)

    def stage() -> bool:
        return governance.stage_policy_change(
            actor_id=42, generation=7, requested=requested, expected_revision=expected_revision,
            evidence=EVIDENCE, password='fixture', code='123456',
        )

    if changed is None:
        with pytest.raises(governance.LockoutGovernanceDenied):
            stage()
        proof.assert_not_called()
        event.assert_not_called()
    else:
        assert stage() is changed
        proof.assert_called_once()
        assert event.call_args.kwargs['metadata']['new_revision'] == (3 if changed else 2)
        assert store.execute.call_count == (2 if changed else 1)
        store.add.assert_called_once_with(event.return_value)
    store.commit.assert_not_called()


def _user(identifier: int, *, source: str = 'database', super_admin: bool = False, active: bool = True) -> User:
    return User(id=identifier, auth_source=source, is_super_admin=super_admin,
                account_is_active=active, auth_session_version=7, password_hash='fixture')


def test_manual_unlock_role_target_boundaries() -> None:
    actor = _user(1, super_admin=True)
    assert governance.can_unlock_account(actor, _user(2))
    assert not governance.can_unlock_account(actor, actor)
    assert not governance.can_unlock_account(actor, _user(2, source='ldap_directory'))
    assert not governance.can_unlock_account(actor, _user(2, super_admin=True))
    assert not governance.can_unlock_account(actor, _user(2, active=False))
    assert not governance.can_unlock_account(_user(3), _user(2))
    assert not governance.can_view_lockout(_user(3), _user(2))


@pytest.mark.parametrize('stale', (False, True))
def test_unlock_only_exact_committed_deadline(monkeypatch: pytest.MonkeyPatch, stale: bool) -> None:
    actor, target = _user(1, super_admin=True), _user(2)
    now = datetime.now(UTC)
    failures = (now - timedelta(seconds=1),) * 10
    deadline = failures[-1] + timedelta(minutes=15)
    state = LockoutState(failures, locked_until=deadline)
    record = AuthenticationAccountLockout(
        user_id=2, policy_revision=5, failure_times=[item.isoformat() for item in failures], locked_until=deadline
    )
    context = LockedAccountState(2, 5, record, inspect_state(LockoutMode.ENFORCED, state, now=now), now)
    store = Mock()
    monkeypatch.setattr(governance, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(governance, '_lock_users', Mock(return_value={1: actor, 2: target}))
    monkeypatch.setattr(governance, '_validate_actor', Mock(return_value=actor))
    monkeypatch.setattr(governance, 'lock_account_state', Mock(return_value=context))
    proof = Mock()
    monkeypatch.setattr(governance, '_step_up', proof)
    event = Mock(return_value=object())
    monkeypatch.setattr(governance, '_event', event)

    def stage() -> None:
        governance.stage_manual_unlock(
            actor_id=1, generation=7, target_id=2, expected_revision=5,
            expected_deadline=(deadline - timedelta(seconds=1) if stale else deadline).isoformat(),
            evidence=EVIDENCE, password='fixture', code='123456',
        )

    if stale:
        with pytest.raises(governance.LockoutGovernanceDenied):
            stage()
        proof.assert_not_called()
        assert record.locked_until == deadline
    else:
        stage()
        proof.assert_called_once()
        assert record.failure_times == [] and record.locked_until is None and record.cooldown_until is None
        assert target.is_active and target.auth_session_version == 7 and target.password_hash == 'fixture'
        assert event.call_args.kwargs['target_id'] == 2
        store.add.assert_called_once_with(event.return_value)
    store.commit.assert_not_called()


def test_ui_and_route_security_contract() -> None:
    root = Path(__file__).resolve().parents[3]
    security = (root / 'app/access/authentication_security/__init__.py').read_text()
    users = (root / 'app/access/users/routes.py').read_text()
    for source, route, permission in (
        (security, "def save_lockout_policy():", "identity_providers.manage"),
        (users, "def unlock(user_id: int):", "users.reset_password"),
    ):
        assert f"@permission_required('{permission}')" in source.split(route, 1)[0].split('@bp.post(', 1)[-1] or (
            f"@permission_required('{permission}')" in source
        )
        body = source.split(route, 1)[1]
        assert 'validate_csrf(' in body and 'login_fresh()' in body
        assert "parse_authenticated_user_identifier(session.get('_user_id'))" in body
        assert 'db.session.rollback()' in body
    page = (root / 'app/templates/access/authentication_security/partials/_page_content.html').read_text()
    overview = page.split("{% if active_tab == 'overview' %}", 1)[1].split("{% elif active_tab == 'mfa' %}", 1)[0]
    assert '_login_protection_summary.html' in overview
    assert '_login_protection_controls.html' not in overview
    bot, login = page.split("{% elif active_tab == 'bot' %}", 1)[1].split(
        "{% elif active_tab == 'login-protection' %}", 1
    )
    assert '_login_protection_controls.html' not in bot
    assert '_login_protection_controls.html' in login
    assert "tab='login-protection', _anchor='login-protection-control'" in security
    summary = (root / 'app/templates/access/authentication_security/partials/_login_protection_summary.html').read_text()
    assert "tab='login-protection'" in summary
    controls = (root / 'app/templates/access/authentication_security/partials/_login_protection_controls.html').read_text()
    assert 'hx-history="false"' in controls
    assert 'name="csrf_token"' in controls
    assert 'name="lockout_revision"' in controls
    assert 'name="acknowledge_lockout_impact"' in controls
    assert '_lockout_assurance_fields.html' in controls

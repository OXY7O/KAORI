from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.settings.account import actions as account_actions
from app.settings.general import actions as general_actions


class Field:
    def __init__(self, data: str) -> None:
        self.data = data
        self.errors: list[str] = []


class TimezoneFormStub:
    def __init__(
        self,
        *,
        timezone_mode: str = 'automatic',
        timezone: str = 'UTC',
        browser_timezone: str = 'Asia/Jakarta',
        valid: bool = True,
    ) -> None:
        self.timezone_mode = Field(timezone_mode)
        self.timezone = Field(timezone)
        self.browser_timezone = Field(browser_timezone)
        self._valid = valid

    def validate_on_submit(self) -> bool:
        return self._valid


class PasswordFormStub:
    def __init__(self, *, current_password: str, new_password: str, valid: bool = True) -> None:
        self.current_password = Field(current_password)
        self.new_password = Field(new_password)
        self._valid = valid

    def validate(self) -> bool:
        return self._valid


class UserStub:
    def __init__(self, *, password: str = 'CurrentPassphrase123!') -> None:
        self.id = 41
        self.password = password
        self.auth_session_version = 7

    def check_password(self, value: str) -> bool:
        return value == self.password

    def set_password(self, value: str) -> None:
        self.password = value
        self.auth_session_version += 1


def _feedback(**_kwargs):
    return {'notification_deck_visible': False}


def _wire_general_action_dependencies(monkeypatch: pytest.MonkeyPatch, commits: list[str]) -> None:
    monkeypatch.setattr(
        general_actions,
        'db',
        SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append('commit'))),
    )
    monkeypatch.setattr(general_actions, 'url_for', lambda *_args, **_kwargs: '/settings/general')
    monkeypatch.setattr(general_actions, 'create_transient_feedback', _feedback)
    monkeypatch.setattr(general_actions, 'record_operational_activity', _feedback)


def _wire_account_action_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    commits: list[str],
    session_preservations: list[int],
    activities: list[dict[str, object]],
) -> None:
    monkeypatch.setattr(
        account_actions,
        'db',
        SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append('commit'))),
    )
    monkeypatch.setattr(account_actions, 'url_for', lambda *_args, **_kwargs: '/settings/account')
    monkeypatch.setattr(account_actions, 'create_transient_feedback', _feedback)
    monkeypatch.setattr(
        account_actions,
        'preserve_current_session_after_password_change',
        lambda user: session_preservations.append(user.id),
    )

    def record_activity(**kwargs):
        activities.append(kwargs)
        return {'notification_deck_visible': False}

    monkeypatch.setattr(account_actions, 'record_operational_activity', record_activity)


def test_timezone_preference_commits_valid_state_and_records_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    commits: list[str] = []
    _wire_general_action_dependencies(monkeypatch, commits)
    user = SimpleNamespace(id=17, timezone_mode='manual', timezone='UTC')
    form = TimezoneFormStub()

    result = general_actions.save_timezone_preference(user=user, form=form, is_htmx=True)

    assert result.saved is True
    assert user.timezone_mode == 'automatic'
    assert user.timezone == 'Asia/Jakarta'
    assert commits == ['commit']


def test_timezone_preference_rejects_invalid_zone_without_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    commits: list[str] = []
    _wire_general_action_dependencies(monkeypatch, commits)
    user = SimpleNamespace(id=17, timezone_mode='manual', timezone='UTC')
    form = TimezoneFormStub(browser_timezone='Not/A-Timezone')

    result = general_actions.save_timezone_preference(user=user, form=form, is_htmx=True)

    assert result.saved is False
    assert user.timezone_mode == 'manual'
    assert user.timezone == 'UTC'
    assert form.timezone.errors == ['The selected or detected browser timezone is not a valid IANA timezone.']
    assert commits == []


def test_browser_timezone_sync_commits_only_effective_automatic_change(monkeypatch: pytest.MonkeyPatch) -> None:
    commits: list[str] = []
    _wire_general_action_dependencies(monkeypatch, commits)
    user = SimpleNamespace(id=17, timezone_mode='automatic', timezone='UTC')

    updated = general_actions.sync_browser_timezone_preference(user=user, browser_timezone='Asia/Jakarta')
    unchanged = general_actions.sync_browser_timezone_preference(user=user, browser_timezone='Asia/Jakarta')

    assert updated == ('updated', 'Asia/Jakarta')
    assert unchanged == ('unchanged', 'Asia/Jakarta')
    assert user.timezone == 'Asia/Jakarta'
    assert commits == ['commit']


def test_password_change_commits_then_preserves_current_session_and_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    commits: list[str] = []
    session_preservations: list[int] = []
    activities: list[dict[str, object]] = []
    _wire_account_action_dependencies(monkeypatch, commits, session_preservations, activities)
    user = UserStub()
    form = PasswordFormStub(
        current_password='CurrentPassphrase123!',
        new_password='ReplacementPassphrase456!',
    )

    result = account_actions.process_password_change(
        user=user,
        form=form,
        auth_source='database',
        is_htmx=False,
    )

    assert result.saved is True
    assert user.password == 'ReplacementPassphrase456!'
    assert user.auth_session_version == 8
    assert commits == ['commit']
    assert session_preservations == [41]
    assert len(activities) == 1
    assert activities[0]['event_type'] == 'account_security'
    assert activities[0]['status'] == 'success'
    assert activities[0]['metadata']['session_effect'] == 'other_sessions_revoked'


@pytest.mark.parametrize(
    ('auth_source', 'current_password', 'new_password', 'expected_reason'),
    [
        ('oidc', 'CurrentPassphrase123!', 'ReplacementPassphrase456!', 'external_credential_owner'),
        ('database', 'WrongPassphrase123!', 'ReplacementPassphrase456!', 'current_password_mismatch'),
        ('database', 'CurrentPassphrase123!', 'CurrentPassphrase123!', 'current_password_reuse'),
    ],
)
def test_password_rejections_do_not_commit_or_preserve_session(
    monkeypatch: pytest.MonkeyPatch,
    auth_source: str,
    current_password: str,
    new_password: str,
    expected_reason: str,
) -> None:
    commits: list[str] = []
    session_preservations: list[int] = []
    activities: list[dict[str, object]] = []
    _wire_account_action_dependencies(monkeypatch, commits, session_preservations, activities)
    user = UserStub()
    form = PasswordFormStub(current_password=current_password, new_password=new_password)

    result = account_actions.process_password_change(
        user=user,
        form=form,
        auth_source=auth_source,
        is_htmx=True,
    )

    assert result.saved is False
    assert user.password == 'CurrentPassphrase123!'
    assert user.auth_session_version == 7
    assert commits == []
    assert session_preservations == []
    assert len(activities) == 1
    assert activities[0]['metadata']['reason_code'] == expected_reason

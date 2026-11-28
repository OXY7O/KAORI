"""Read-only effective Account posture and bounded personal evidence (#5323)."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.access.authentication.session_lifecycle import SessionPolicy
from app.models import Notification
from app.settings.account import queries


@pytest.mark.parametrize(
    ('mode', 'enrolled', 'privileged', 'label'),
    [
        ('disabled', True, True, 'Disabled by Policy'),
        ('optional', False, False, 'Not Enrolled'),
        ('optional', True, False, 'Challenge Required'),
        ('required_privileged', False, False, 'Not Enrolled'),
        ('required_privileged', False, True, 'Enrollment Required'),
        ('required_all', False, False, 'Enrollment Required'),
        ('required_all', True, True, 'Challenge Required'),
    ],
)
def test_personal_posture_uses_effective_policy(mode: str, enrolled: bool, privileged: bool, label: str) -> None:
    policy = SessionPolicy(
        privileged_idle_minutes=10, privileged_absolute_hours=3,
        regular_idle_minutes=25, regular_absolute_hours=6,
    )
    result = queries.build_personal_security_posture(
        mode=mode, enrolled=enrolled, privileged=privileged, session_policy=policy
    )
    assert result.mfa_label == label
    assert result.mfa_policy == mode
    assert result.idle_minutes == (10 if privileged else 25)
    assert result.absolute_hours == (3 if privileged else 6)
    assert result.remember_label == ('Not Permitted' if privileged else 'Permitted by Policy')


def test_regular_remember_policy_disabled() -> None:
    result = queries.build_personal_security_posture(
        mode='optional', enrolled=False, privileged=False, session_policy=SessionPolicy(regular_remember=False),
    )
    assert result.remember_label == 'Disabled by Policy'


def test_profile_selects_only_policy_and_enabled_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    store = Mock()
    store.execute.return_value.scalar_one_or_none.side_effect = ['required_all', True]
    monkeypatch.setattr(queries, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(queries, 'read_session_policy', lambda: SessionPolicy())
    result = queries.read_personal_security_posture(SimpleNamespace(id=42, is_admin_level=False))
    assert result.mfa_label == 'Challenge Required'
    first, second = [call.args[0] for call in store.execute.call_args_list]
    assert 'mfa_mode' in str(first) and 'bot_secret_key' not in str(first)
    assert 'enabled' in str(second) and 'totp_secret' not in str(second) and 'recovery_hashes' not in str(second)
    assert 42 in second.compile().params.values()
    store.commit.assert_not_called()


@pytest.mark.parametrize(
    ('event_type', 'metadata', 'label'),
    [
        ('account_security', {'security_action': 'password_change'}, 'Password Change Recorded'),
        ('authentication', {'audit_schema': 'authentication.security.v1', 'access_action': 'mfa_recovery_regenerated',
                            'target_user_id': 42}, 'Recovery Codes Regenerated'),
        ('authentication', {'audit_schema': 'authentication.security.v1', 'access_action': 'mfa_recovery_regenerated',
                            'target_user_id': 43}, None),
        ('authentication', {'audit_schema': 'authentication.security.v1', 'access_action': 'mfa_policy_changed',
                            'target_user_id': 42}, None),
    ],
)
def test_personal_history_label_allowlist(event_type: str, metadata: dict[str, object], label: str | None) -> None:
    event = Notification()
    event.user_id = 42
    event.event_type = event_type
    event.metadata_json = metadata
    event.title = 'Recorded Event'
    event.status = 'success'
    assert queries.personal_security_event_label(event) == label
    assert queries.authentication_event_kind(event) == 'unknown'


def test_personal_query_fences_user_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    query = Mock()
    query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    monkeypatch.setattr(queries, 'Notification', SimpleNamespace(
        query=query, user_id=Notification.user_id, event_type=Notification.event_type,
        metadata_json=Notification.metadata_json, created_at=Notification.created_at, id=Notification.id,
    ))
    assert queries.recent_authentication_events(42, limit=100) == []
    conditions = query.filter.call_args.args
    assert 42 in conditions[0].compile().params.values()
    assert 'password_change' in conditions[1].compile().params.values()
    query.filter.return_value.order_by.return_value.limit.assert_called_once_with(5)


def test_account_tab_scopes_reads_and_retains_shared_layout() -> None:
    root = Path(__file__).resolve().parents[3]
    route = (root / 'app/settings/routes.py').read_text(encoding='utf-8')
    profile = (root / 'app/templates/settings/account/partials/_profile_cards.html').read_text(encoding='utf-8')
    assert "if active_tab == 'mfa':\n        mfa_factor = account_mfa_factor(user.id)" in route
    assert "read_personal_security_posture(user) if active_tab == 'profile' else None" in route
    assert "recent_authentication_events(user.id) if active_tab == 'activity' else []" in route
    assert 'data-account-security-posture="effective"' in profile
    assert 'personal_security_posture.idle_minutes' in profile
    assert 'personal_security_posture.remember_label' in profile
    assert '<form' not in profile

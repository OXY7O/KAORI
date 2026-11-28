"""Account projection must not turn session expiry into a failed sign-in (#5320)."""

import pytest

from app.models import Notification
from app.settings.account.queries import authentication_activity_summary, authentication_event_kind


def _event(action: str | None, status: str, title: str = 'Recorded event') -> Notification:
    event = Notification()
    event.metadata_json = {'access_action': action} if action is not None else {}
    event.status = status
    event.title = title
    return event


@pytest.mark.parametrize(
    ('action', 'status', 'title', 'expected'),
    [
        ('login', 'success', 'User signed in', 'success'),
        ('login', 'error', 'Sign-in attempt failed', 'failed'),
        ('logout', 'success', 'User signed out', 'sign_out'),
        ('session_expired', 'warning', 'Session expired', 'expired'),
        ('session_policy_changed', 'success', 'Policy changed', 'unknown'),
        ('other', 'error', 'User signed out', 'unknown'),
        ('login', 'warning', 'Unknown result', 'unknown'),
        (None, 'success', 'User signed out', 'sign_out'),
        (None, 'success', 'User signed in', 'success'),
        (None, 'error', 'Sign-in attempt failed', 'failed'),
        (None, 'error', 'Unknown event', 'unknown'),
    ],
)
def test_account_authentication_event_kind(action: str | None, status: str, title: str, expected: str) -> None:
    assert authentication_event_kind(_event(action, status, title)) == expected


def test_account_latest_five_summary_reconciles_without_false_sign_in() -> None:
    events = [
        _event('session_expired', 'warning'),
        _event('login', 'success'),
        _event('login', 'error'),
        _event('logout', 'success'),
        _event('session_policy_changed', 'success'),
    ]
    assert authentication_activity_summary(events) == {
        'total': 5,
        'success': 1,
        'failed': 1,
        'sign_out': 1,
        'expired': 1,
        'unknown': 1,
    }


def test_account_empty_summary_reconciles() -> None:
    assert authentication_activity_summary([]) == {
        'total': 0,
        'success': 0,
        'failed': 0,
        'sign_out': 0,
        'expired': 0,
        'unknown': 0,
    }

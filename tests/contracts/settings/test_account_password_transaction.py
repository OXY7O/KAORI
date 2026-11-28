"""Self-service password mutation evidence and generation boundary (#5329)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, session
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.session_lifecycle import SessionPolicy
from app.models import User
from app.settings.account import actions


def _actor() -> User:
    now = datetime.now(UTC)
    user = User(
        id=42,
        auth_source='database',
        account_is_active=True,
        is_super_admin=True,
        auth_session_version=8,
        auth_session_issued_at=now,
        auth_session_activity_at=now,
    )
    user.set_password('original-passphrase-test')
    return user


def _form() -> Mock:
    form = Mock()
    form.validate.return_value = True
    form.current_password.data = 'original-passphrase-test'
    form.new_password.data = 'replacement-passphrase-test'
    form.current_password.errors = []
    form.new_password.errors = []
    return form


@pytest.mark.parametrize('failure', ('none', 'stale', 'audit', 'commit'))
def test_password_success_evidence_and_session_follow_commit(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    app.secret_key = 'isolated-test'
    user = _actor()
    store = Mock()
    store.execute.return_value.scalar_one_or_none.return_value = None if failure == 'stale' else user
    if failure == 'commit':
        store.commit.side_effect = SQLAlchemyError('commit boundary')
    stage = Mock(return_value={'notification_deck_visible': True})
    if failure == 'audit':
        stage.side_effect = SQLAlchemyError('audit boundary')
    preserve = Mock()
    timeline = Mock()
    timeline.attach_mock(stage, 'stage')
    timeline.attach_mock(store.commit, 'commit')
    timeline.attach_mock(preserve, 'preserve')
    monkeypatch.setattr(actions, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(actions, 'stage_operational_activity', stage)
    monkeypatch.setattr(actions, 'read_session_policy', lambda: SessionPolicy())
    monkeypatch.setattr(actions, 'preserve_current_session_after_password_change', preserve)
    monkeypatch.setattr(actions, 'create_transient_feedback', Mock(return_value={'status': 'error'}))
    monkeypatch.setattr(actions, 'ChangePasswordForm', Mock())
    monkeypatch.setattr(actions, 'url_for', lambda *args, **kwargs: '/settings/account?tab=credentials')
    with app.test_request_context('/settings/account?tab=credentials', method='POST'):
        session['_user_id'] = '42:8'
        result = actions.process_password_change(user=user, form=_form(), auth_source='database', is_htmx=True)
    statement = str(store.execute.call_args.args[0]).lower()
    assert 'users.auth_session_version' in statement
    assert 'users.password_hash' in statement
    assert 'for update' in statement
    if failure == 'none':
        assert result.saved
        assert [call[0] for call in timeline.mock_calls] == ['stage', 'commit', 'preserve']
        assert stage.call_args.kwargs['metadata']['auth_session_version'] == 9
        preserve.assert_called_once_with(user_id=42, issued_session_version=9)
        store.rollback.assert_not_called()
    else:
        assert not result.saved
        store.rollback.assert_called_once()
        preserve.assert_not_called()
        if failure == 'stale':
            stage.assert_not_called()
        if failure != 'commit':
            store.commit.assert_not_called()

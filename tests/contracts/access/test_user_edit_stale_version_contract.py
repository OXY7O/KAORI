"""User Edit must reject stale administrative intent under a serialized row lock."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.access.users.service import user_version_matches, user_version_token


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        updated_at=datetime(2026, 10, 11, tzinfo=UTC),
        role_id=2,
        account_is_active=True,
        is_super_admin=False,
        auth_session_version=1,
        deleted_at=None,
    )


def test_user_version_token_reflects_role_lifecycle_and_credential_changes() -> None:
    user = _user()
    token = user_version_token(user)
    assert user_version_matches(user, token)
    assert not user_version_matches(user, None)
    for field, value in (
        ('role_id', 3),
        ('account_is_active', False),
        ('is_super_admin', True),
        ('auth_session_version', 2),
        ('deleted_at', datetime(2026, 10, 12, tzinfo=UTC)),
        ('updated_at', user.updated_at + timedelta(seconds=1)),
    ):
        candidate = _user()
        setattr(candidate, field, value)
        assert not user_version_matches(candidate, token)


def test_user_edit_uses_committed_version_before_write() -> None:
    root = Path(__file__).resolve().parents[3]
    route = (root / 'app/access/users/routes.py').read_text(encoding='utf-8')
    form = (root / 'app/access/users/forms.py').read_text(encoding='utf-8')
    service = (root / 'app/access/users/service.py').read_text(encoding='utf-8')
    template = (root / 'app/templates/access/users/form.html').read_text(encoding='utf-8')
    edit = route.split('def edit(user_id: int):', 1)[1].split('\n@bp.', 1)[0]
    assert 'user_version = HiddenField()' in form
    assert '{{ form.hidden_tag() }}' in template
    assert 'form.user_version.data = user_version_token(user)' in edit
    assert 'locked_user = lock_user_for_mutation(user_id)' in edit
    assert 'if not user_version_matches(user, form.user_version.data):' in edit
    assert edit.index('user_version_matches(') < edit.index('create_or_update_user(form, user)')
    assert 'rollback_user_edit_transaction()' in edit
    rollback = service.split('def rollback_user_edit_transaction() -> None:', 1)[1]
    rollback = rollback.split('\ndef ', 1)[0]
    assert 'db.session.rollback()' in rollback
    assert edit.index('rollback_user_edit_transaction()') < edit.index(
        'user = get_user(user_id)', edit.index('rollback_user_edit_transaction()')
    )
    assert 'db.session.rollback()' not in edit
    assert 'form.user_version.errors' in edit
    assert 'with_for_update()' in service
    assert '.populate_existing()' in service

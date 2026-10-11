"""User lifecycle and reset writes must rollback with audit on SQL transaction failure."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app.access.users import service


@pytest.mark.parametrize('operation', [
    'activate_user_account',
    'deactivate_user_account',
    'reset_user_password',
    'restore_user_account',
    'delete_user_account',
])
def test_user_lifecycle_db_failure_rolls_back(monkeypatch, operation: str) -> None:
    class Session:
        rolls = 0

        def commit(self):
            raise OperationalError('UPDATE users', {}, RuntimeError('injected failed commit'))

        def rollback(self):
            self.rolls += 1

    session = Session()
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(service, 'record_admin_event', lambda **kwargs: None)
    user = SimpleNamespace(
        username='test-user', account_is_active=True, deleted_at=None,
        updated_at=datetime(2026, 10, 12, tzinfo=UTC),
        set_password=lambda password: None,
    )
    kwargs = {'actor': object(), 'user': user}
    if operation == 'reset_user_password':
        kwargs['password'] = 'a valid new password'

    with pytest.raises(OperationalError):
        getattr(service, operation)(**kwargs)
    assert session.rolls == 1


def test_route_feedback_preserves_fail_closed_lifecycle_and_reset_forms() -> None:
    source = (Path(__file__).resolve().parents[3] /
              'app/access/users/routes.py').read_text(encoding='utf-8')
    for method, call in (
        ('activate', 'activate_user_account('),
        ('deactivate', 'deactivate_user_account('),
        ('restore', 'restore_user_account('),
        ('delete', 'delete_user_account('),
    ):
        route = source.split(f'def {method}(', 1)[1].split('\n@bp.', 1)[0]
        assert call in route
        assert 'except SQLAlchemyError:' in route
        assert 'return reject(' in route
        assert "status='error'" in route
    reset = source.split('def reset_password(', 1)[1].split('\n@bp.', 1)[0]
    assert 'except SQLAlchemyError:' in reset
    assert 'form.password.errors' in reset
    assert "render_template('access/users/reset_password.html'" in reset

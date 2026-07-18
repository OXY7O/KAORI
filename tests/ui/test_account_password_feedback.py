from __future__ import annotations

import os

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Notification, Role, User  # noqa: E402
from app.rbac.service import seed_default_rbac  # noqa: E402


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _create_local_user() -> int:
    seed_default_rbac()
    viewer = Role.query.filter_by(name='viewer').one()
    user = User(
        username='account-password-user',
        email='account-password-user@example.test',
        role=viewer.name,
        role_id=viewer.id,
        account_is_active=True,
        auth_source='database',
    )
    user.set_password('CurrentPassword123!')
    db.session.add(user)
    db.session.commit()
    return user.id


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def test_password_change_uses_toast_without_duplicate_inline_success(app) -> None:
    with app.app_context():
        user_id = _create_local_user()

    client = app.test_client()
    _login(client, user_id)

    response = client.post(
        '/settings/account?tab=credentials',
        data={
            'current_password': 'CurrentPassword123!',
            'new_password': 'NewPassword456!',
            'confirm_password': 'NewPassword456!',
            'submit_password': '1',
        },
        headers={'HX-Request': 'true'},
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Account password updated' in body
    assert 'Password updated successfully' not in body
    assert 'Your local database account password has been changed.' not in body
    assert response.headers.get('HX-Trigger') is not None

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user is not None
        assert user.check_password('NewPassword456!')

        activity = Notification.query.filter_by(
            user_id=user_id,
            event_type='account_security',
        ).one()
        assert activity.status == 'success'
        assert activity.metadata_json is not None
        assert activity.metadata_json['security_action'] == 'password_change'
        assert 'NewPassword456!' not in str(activity.metadata_json)

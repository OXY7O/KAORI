from __future__ import annotations

import os

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def test_user_without_normalized_role_gets_kaori_violet_access_state(app) -> None:
    with app.app_context():
        user = User(
            username='unassigned-user',
            email='unassigned@example.test',
            role='unassigned',
            role_id=None,
            account_is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    response = client.get('/settings/roles')
    assert response.status_code == 403
    assert b'Access role unavailable' in response.data
    assert b'No normalized role' in response.data
    assert b'bg-kaori-primary' in response.data
    assert b'Back to Welcome' in response.data
    assert b'Access administrator action' in response.data

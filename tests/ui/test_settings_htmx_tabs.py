from __future__ import annotations

import os

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.rbac.service import seed_default_rbac  # noqa: E402


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _login_admin(app) -> tuple[object, int]:
    with app.app_context():
        seed_default_rbac()
        admin = Role.query.filter_by(name='admin').one()
        user = User(
            username='settings-admin',
            email='settings-admin@example.test',
            role=admin.name,
            role_id=admin.id,
            account_is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True
    return client, user_id


@pytest.mark.parametrize(
    ('path', 'page_id', 'active_label'),
    (
        ('/settings/general?tab=time-locale', 'general-settings-page', 'Time Zone'),
        ('/settings/general?tab=regional-format', 'general-settings-page', 'Regional Format'),
        ('/settings/general?tab=system-information', 'general-settings-page', 'System Information'),
        ('/settings/account?tab=profile', 'account-authentication-page', 'Account Profile & Access'),
        ('/settings/account?tab=activity', 'account-authentication-page', 'Recent Authentication Activity'),
        ('/settings/account?tab=credentials', 'account-authentication-page', 'Credential Management'),
    ),
)
def test_settings_tab_htmx_requests_return_workspace_partial(
    app,
    path: str,
    page_id: str,
    active_label: str,
) -> None:
    client, _ = _login_admin(app)

    response = client.get(path, headers={'HX-Request': 'true'})

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f'id="{page_id}"' in body
    assert '<!DOCTYPE html>' not in body
    assert active_label in body
    assert 'aria-selected="true"' in body

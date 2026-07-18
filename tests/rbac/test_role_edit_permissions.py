from __future__ import annotations

import os

import pytest
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import MultiDict

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Notification, Permission, Role, User  # noqa: E402
from app.rbac.service import expand_permission_keys, replace_role_permissions, seed_default_rbac  # noqa: E402


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _build_self_managed_custom_role() -> tuple[int, int, list[int]]:
    seed_default_rbac()
    role = Role(
        name='custom_access_admin',
        display_name='Custom Access Admin',
        description='Regression role for permission editing.',
        is_system=False,
        is_active=True,
    )
    db.session.add(role)
    db.session.flush()

    baseline_keys = {'welcome.view', 'settings.view', 'roles.view', 'roles.manage'}
    baseline_permissions = Permission.query.filter(Permission.key.in_(baseline_keys)).all()
    baseline_ids = [permission.id for permission in baseline_permissions]
    replace_role_permissions(role, baseline_ids)

    actor = User(
        username='role-editor',
        email='role-editor@example.test',
        role=role.name,
        role_id=role.id,
        account_is_active=True,
    )
    db.session.add(actor)
    db.session.commit()
    return actor.id, role.id, baseline_ids


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def _role_payload(permission_ids: list[int]) -> MultiDict:
    return MultiDict(
        [
            ('name', 'custom_access_admin'),
            ('display_name', 'Custom Access Admin'),
            ('description', 'Regression role for permission editing.'),
            ('is_active', 'y'),
            *[('permission_ids', str(permission_id)) for permission_id in permission_ids],
        ]
    )


def test_edit_custom_role_accepts_every_registered_permission(app) -> None:
    with app.app_context():
        actor_id, role_id, baseline_ids = _build_self_managed_custom_role()
        registered_permissions = [
            (permission.id, permission.key)
            for permission in Permission.query.order_by(Permission.id.asc()).all()
        ]
        baseline_keys = {
            permission.key
            for permission in Permission.query.filter(Permission.id.in_(baseline_ids)).all()
        }

    client = app.test_client()
    _login(client, actor_id)

    for permission_id, permission_key in registered_permissions:
        response = client.post(
            f'/settings/roles/{role_id}/edit',
            data=_role_payload([*baseline_ids, permission_id]),
            follow_redirects=True,
        )

        assert response.status_code == 200, permission_key
        assert response.request.path == '/settings/roles', permission_key
        assert b'Custom role updated' in response.data, permission_key
        assert b'access scope was updated' in response.data, permission_key
        assert b'Custom role updated successfully.' not in response.data, permission_key

        with app.app_context():
            db.session.expire_all()
            role = db.session.get(Role, role_id)
            assert role is not None
            assert role.permission_keys() == expand_permission_keys(
                baseline_keys | {permission_key}
            ), permission_key
            notification = Notification.query.order_by(Notification.id.desc()).first()
            assert notification is not None
            assert notification.event_type == 'rbac_role_updated'
            assert notification.status == 'success'
            assert notification.metadata_json['module'] == 'rbac'
            assert notification.metadata_json['target_id'] == role_id


def test_edit_custom_role_rolls_back_database_failure(app, monkeypatch) -> None:
    with app.app_context():
        actor_id, role_id, baseline_ids = _build_self_managed_custom_role()
        original_keys = db.session.get(Role, role_id).permission_keys()

    def fail_permission_update(_role, _permission_ids):
        raise SQLAlchemyError('forced permission update failure')

    monkeypatch.setattr('app.settings.routes.replace_role_permissions', fail_permission_update)

    client = app.test_client()
    _login(client, actor_id)
    response = client.post(
        f'/settings/roles/{role_id}/edit',
        data=_role_payload(baseline_ids),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Custom role update failed' in response.data
    assert b'No role changes were saved.' in response.data
    assert b'The custom role could not be updated.' not in response.data

    with app.app_context():
        db.session.expire_all()
        role = db.session.get(Role, role_id)
        assert role is not None
        assert role.permission_keys() == original_keys
        notification = Notification.query.order_by(Notification.id.desc()).first()
        assert notification is not None
        assert notification.event_type == 'rbac_role_update_failed'
        assert notification.status == 'error'

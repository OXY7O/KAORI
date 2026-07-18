from __future__ import annotations

import os

import pytest
from werkzeug.datastructures import MultiDict

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import AuditEvent, Notification, Permission, Role, User  # noqa: E402
from app.rbac.service import seed_default_rbac  # noqa: E402


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def _create_admin_actor() -> tuple[int, int, int]:
    seed_default_rbac()
    admin = Role.query.filter_by(name='admin').one()
    viewer = Role.query.filter_by(name='viewer').one()
    actor = User(
        username='rbac-admin',
        email='rbac-admin@example.test',
        role=admin.name,
        role_id=admin.id,
        account_is_active=True,
    )
    db.session.add(actor)
    db.session.commit()
    permission = Permission.query.filter_by(key='welcome.view').one()
    return actor.id, viewer.id, permission.id


def test_role_create_clone_and_delete_use_toast_and_activity_audit(app) -> None:
    with app.app_context():
        actor_id, viewer_id, permission_id = _create_admin_actor()

    client = app.test_client()
    _login(client, actor_id)

    create_response = client.post(
        '/settings/roles/new',
        data=MultiDict(
            [
                ('name', 'operations_support'),
                ('display_name', 'Operations Support'),
                ('description', 'Created by notification regression test.'),
                ('is_active', 'y'),
                ('permission_ids', str(permission_id)),
            ]
        ),
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert b'Custom role created' in create_response.data
    assert b'Custom role created successfully.' not in create_response.data

    clone_response = client.post(
        f'/settings/roles/{viewer_id}/clone',
        data=MultiDict(
            [
                ('name', 'viewer_clone_test'),
                ('display_name', 'Viewer Clone Test'),
                ('description', 'Clone notification test.'),
                ('is_active', 'y'),
                ('permission_ids', str(permission_id)),
            ]
        ),
        follow_redirects=True,
    )
    assert clone_response.status_code == 200
    assert b'Default role cloned' in clone_response.data

    with app.app_context():
        target = Role.query.filter_by(name='operations_support').one()
        target_id = target.id

    delete_response = client.post(
        f'/settings/roles/{target_id}/delete',
        data={'role_id': str(target_id)},
        follow_redirects=True,
    )
    assert delete_response.status_code == 200
    assert b'Custom role deleted' in delete_response.data
    assert b'was deleted.' not in delete_response.data

    with app.app_context():
        event_types = [
            item.event_type
            for item in Notification.query.order_by(Notification.id.asc()).all()
        ]
        assert event_types == [
            'rbac_role_created',
            'rbac_role_cloned',
            'rbac_role_deleted',
        ]
        for item in Notification.query.all():
            assert item.metadata_json['module'] == 'rbac'
            assert item.action_url == '/settings/roles'

        audit_actions = {
            event.action for event in AuditEvent.query.order_by(AuditEvent.id.asc()).all()
        }
        assert {'role.created', 'role.cloned', 'role.deleted'} <= audit_actions


def test_rbac_routes_do_not_use_flask_flash_messages() -> None:
    source = open('app/settings/routes.py', encoding='utf-8').read()
    role_routes = source[source.index("@bp.route('/roles')"):source.index("@bp.route('/reports')")]
    assert 'flash(' not in role_routes
    assert 'role_access_feedback(' in role_routes

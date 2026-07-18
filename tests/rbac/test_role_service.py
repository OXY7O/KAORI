from __future__ import annotations

import os

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import IdentityProvider, Permission, Role, RolePermission, User  # noqa: E402
from app.rbac.defaults import DEFAULT_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS  # noqa: E402
from app.rbac.service import (  # noqa: E402
    expand_permission_keys,
    get_role_delete_blockers,
    normalize_role_slug,
    replace_role_permissions,
    seed_default_rbac,
)


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def test_seed_default_rbac_converges_system_roles(app) -> None:
    result = seed_default_rbac()
    assert result == {'permissions': len(DEFAULT_PERMISSIONS), 'roles': 5}

    roles = {role.name: role for role in Role.query.all()}
    assert set(roles) == {'viewer', 'operator', 'editor', 'admin', 'auditor'}

    viewer = roles['viewer']
    canonical_key = next(iter(DEFAULT_ROLE_PERMISSIONS['viewer']))
    canonical_link = next(
        role_permission
        for role_permission in viewer.role_permissions
        if role_permission.permission.key == canonical_key
    )
    db.session.delete(canonical_link)

    reveal_permission = Permission.query.filter_by(key='kubernetes_secrets.reveal').one()
    db.session.add(RolePermission(role_id=viewer.id, permission_id=reveal_permission.id))
    db.session.commit()

    seed_default_rbac()
    db.session.expire_all()

    for role_name, expected_keys in DEFAULT_ROLE_PERMISSIONS.items():
        role = Role.query.filter_by(name=role_name).one()
        assert role.is_system is True
        assert role.is_active is True
        assert role.permission_keys() == expected_keys


def test_custom_role_dependencies_are_added(app) -> None:
    seed_default_rbac()
    role = Role(
        name='support_operator',
        display_name='Support Operator',
        description='Custom support role.',
        is_system=False,
        is_active=True,
    )
    db.session.add(role)
    db.session.flush()

    manage_users = Permission.query.filter_by(key='users.manage').one()
    effective_ids = replace_role_permissions(role, [manage_users.id])
    db.session.commit()
    db.session.expire_all()

    role = Role.query.filter_by(name='support_operator').one()
    assert role.permission_keys() == {'users.manage', 'users.view'}
    assert len(effective_ids) == 2
    assert expand_permission_keys({'reports.generate'}) == {'reports.generate', 'reports.view'}


def test_system_role_permissions_cannot_be_replaced(app) -> None:
    seed_default_rbac()
    viewer = Role.query.filter_by(name='viewer').one()

    with pytest.raises(ValueError, match='System role permissions are code-owned'):
        replace_role_permissions(viewer, [])


def test_role_delete_blockers_include_users_and_identity_providers(app) -> None:
    seed_default_rbac()
    role = Role(
        name='external_operator',
        display_name='External Operator',
        is_system=False,
        is_active=True,
    )
    db.session.add(role)
    db.session.flush()

    user = User(
        username='role-user',
        email='role-user@example.test',
        role=role.name,
        role_id=role.id,
    )
    provider = IdentityProvider(
        key='test-oidc',
        display_name='Test OIDC',
        provider_type='google_oidc',
        default_role_id=role.id,
    )
    db.session.add_all([user, provider])
    db.session.commit()

    assert get_role_delete_blockers(role) == {
        'assigned_users': 1,
        'identity_providers': 1,
    }


def test_normalize_role_slug() -> None:
    assert normalize_role_slug('  Support-Operator / L2  ') == 'support_operator_l2'

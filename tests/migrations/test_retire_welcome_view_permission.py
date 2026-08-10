from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / 'migrations/versions/20260810_retire_welcome_view.py'


def _load_migration():
    spec = importlib.util.spec_from_file_location('kaori_retire_welcome_view_migration', MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema(engine: sa.Engine) -> tuple[sa.Table, sa.Table, sa.Table]:
    metadata = sa.MetaData()
    permissions = sa.Table(
        'permissions',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('key', sa.String(120), unique=True, nullable=False),
        sa.Column('module', sa.String(80), nullable=False),
        sa.Column('action', sa.String(80), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    roles = sa.Table(
        'roles',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(80), unique=True, nullable=False),
    )
    role_permissions = sa.Table(
        'role_permissions',
        metadata,
        sa.Column('role_id', sa.Integer, nullable=False),
        sa.Column('permission_id', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)
    return permissions, roles, role_permissions


def test_upgrade_removes_non_enforcing_permission_and_assignments(monkeypatch) -> None:
    migration = _load_migration()
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    permissions, roles, role_permissions = _schema(engine)
    now = datetime.now(UTC)

    with engine.begin() as connection:
        connection.execute(
            roles.insert(),
            [
                {'id': 1, 'name': 'viewer'},
                {'id': 2, 'name': 'custom-role'},
            ],
        )
        connection.execute(
            permissions.insert(),
            [
                {
                    'id': 1,
                    'key': 'welcome.view',
                    'module': 'workspace',
                    'action': 'view',
                    'description': 'legacy',
                    'created_at': now,
                },
                {
                    'id': 2,
                    'key': 'dashboard.view',
                    'module': 'k8s_dashboard',
                    'action': 'view',
                    'description': 'active',
                    'created_at': now,
                },
            ],
        )
        connection.execute(
            role_permissions.insert(),
            [
                {'role_id': 1, 'permission_id': 1, 'created_at': now},
                {'role_id': 2, 'permission_id': 1, 'created_at': now},
                {'role_id': 1, 'permission_id': 2, 'created_at': now},
            ],
        )
        monkeypatch.setattr(migration.op, 'get_bind', lambda: connection)

        migration.upgrade()

        assert (
            connection.scalar(
                sa.select(sa.func.count()).select_from(permissions).where(permissions.c.key == 'welcome.view')
            )
            == 0
        )
        assert (
            connection.scalar(
                sa.select(sa.func.count()).select_from(role_permissions).where(role_permissions.c.permission_id == 1)
            )
            == 0
        )
        assert (
            connection.scalar(
                sa.select(sa.func.count()).select_from(permissions).where(permissions.c.key == 'dashboard.view')
            )
            == 1
        )


def test_downgrade_restores_historical_default_role_contract(monkeypatch) -> None:
    migration = _load_migration()
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    permissions, roles, role_permissions = _schema(engine)

    with engine.begin() as connection:
        connection.execute(
            roles.insert(),
            [
                {'id': 1, 'name': 'viewer'},
                {'id': 2, 'name': 'operator'},
                {'id': 3, 'name': 'editor'},
                {'id': 4, 'name': 'admin'},
                {'id': 5, 'name': 'auditor'},
                {'id': 6, 'name': 'custom-role'},
            ],
        )
        monkeypatch.setattr(migration.op, 'get_bind', lambda: connection)

        migration.downgrade()

        permission_id = connection.scalar(sa.select(permissions.c.id).where(permissions.c.key == 'welcome.view'))
        assert permission_id is not None
        assigned_roles = set(
            connection.scalars(
                sa.select(roles.c.name)
                .join(role_permissions, role_permissions.c.role_id == roles.c.id)
                .where(role_permissions.c.permission_id == permission_id)
            )
        )
        assert assigned_roles == {'viewer', 'operator', 'editor', 'admin', 'auditor'}
